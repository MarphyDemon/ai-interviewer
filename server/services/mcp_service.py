"""MCP 服务注册表与接线层。

职责：
1. 从环境变量 `MCP_SERVERS`（JSON 数组）读取启用的 MCP server，缺省启用内置示例 server
2. 进程级复用 `MCPClient`（避免每次工具调用都重启子进程）
3. 把 MCP 工具转换为 **OpenAI tools 格式**，函数名规范化为 `mcp_<server>_<tool>`
4. 反查真实 server/tool 并转发调用，异常一律收敛为 `ok=False`（不向上抛）

环境变量示例：
    MCP_SERVERS='[{"name":"sample","command":"python","args":["-m","server.mcp_servers.sample_interview_server"],"enabled":true}]'

字段说明（每项）：
    name    必填，server 唯一标识，参与函数名拼接
    command 必填，可执行文件（建议写绝对路径，如 sys.executable）
    args    可选，字符串数组
    enabled 可选，默认 true；显式 false 则该 server 不加载
    timeout 可选，单请求超时秒数，默认 20
    cwd     可选，子进程工作目录，默认仓库根目录
    env     可选，追加到子进程环境变量

注意：本模块只做「注册与转发」，不感知面试上下文；上下文注入由调用方
（`interview_tools.execute_tool`）负责，见 docs/MCP接入方案.md 第 5 节。
"""

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

from server.services.mcp_client import MCPClient, MCPError

# 仓库根目录（server/ 的上一级），作为子进程默认工作目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TIMEOUT = 20.0
# 工具文本回灌上限（与 interview_brain_service 的 4000 字符截断保持一致）
MAX_TEXT_CHARS = 4000
# OpenAI 函数名上限为 64 字符
MAX_FUNCTION_NAME = 64

_NAME_SAFE = re.compile(r"[^0-9a-zA-Z_]")

_clients: dict[str, MCPClient] = {}
_configs: dict[str, dict] = {}
# OpenAI 函数名 → (server name, tool name)，供调用时反查
_name_map: dict[str, tuple[str, str]] = {}
_schemas: list[dict] = []
_loaded = False
_lock = asyncio.Lock()


def _log(message: str) -> None:
    print(f"[MCP Service] {message}", file=sys.stderr)


def _default_servers() -> list[dict]:
    """缺省配置：本仓库内置的离线示例 server。"""
    return [
        {
            "name": "sample",
            "command": sys.executable,
            "args": ["-m", "server.mcp_servers.sample_interview_server"],
            "enabled": True,
        }
    ]


def load_server_configs() -> list[dict]:
    """读取并校验 `MCP_SERVERS`；任何非法配置都降级为内置示例 server。"""
    raw = os.environ.get("MCP_SERVERS", "").strip()
    if not raw:
        return _default_servers()

    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        _log(f"MCP_SERVERS 不是合法 JSON（{e}），回退到内置示例 server")
        return _default_servers()

    if not isinstance(items, list):
        _log("MCP_SERVERS 必须是 JSON 数组，回退到内置示例 server")
        return _default_servers()

    configs: list[dict] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            _log(f"MCP_SERVERS[{idx}] 不是对象，已跳过")
            continue
        name = str(item.get("name") or "").strip()
        command = str(item.get("command") or "").strip()
        if not name or not command:
            _log(f"MCP_SERVERS[{idx}] 缺少 name/command，已跳过")
            continue
        if not item.get("enabled", True):
            _log(f"MCP_SERVERS[{idx}]（{name}）enabled=false，已跳过")
            continue

        args = item.get("args") or []
        if not isinstance(args, list):
            _log(f"MCP_SERVERS[{idx}]（{name}）args 必须是数组，已按空处理")
            args = []
        try:
            timeout = float(item.get("timeout") or DEFAULT_TIMEOUT)
        except (TypeError, ValueError):
            _log(f"MCP_SERVERS[{idx}]（{name}）timeout 非法，使用默认 {DEFAULT_TIMEOUT:.0f}s")
            timeout = DEFAULT_TIMEOUT

        configs.append(
            {
                "name": name,
                "command": command,
                "args": [str(a) for a in args],
                "timeout": timeout,
                "cwd": str(item.get("cwd") or PROJECT_ROOT),
                "env": item.get("env") if isinstance(item.get("env"), dict) else {},
            }
        )
    return configs


def _normalize_name(server: str, tool: str, used: set[str]) -> str:
    """生成合法且唯一的 OpenAI 函数名：`mcp_<server>_<tool>`。"""
    safe = _NAME_SAFE.sub("_", f"mcp_{server}_{tool}")
    safe = re.sub(r"_{2,}", "_", safe).strip("_") or "mcp_tool"
    if len(safe) > MAX_FUNCTION_NAME:
        safe = safe[:MAX_FUNCTION_NAME].rstrip("_") or "mcp_tool"

    base, suffix = safe, 1
    while safe in used:
        suffix += 1
        tail = f"_{suffix}"
        safe = base[: MAX_FUNCTION_NAME - len(tail)].rstrip("_") + tail
    used.add(safe)
    return safe


def _to_openai_schema(fn_name: str, server_name: str, tool: dict) -> dict:
    """MCP tool → OpenAI tools 格式（inputSchema 直接复用为 parameters）。"""
    params = tool.get("inputSchema")
    if not isinstance(params, dict) or params.get("type") != "object":
        # 缺省或非对象 schema 一律退化为无参对象，保证 LLM 侧永远拿到合法 schema
        params = {"type": "object", "properties": {}, "required": []}
    else:
        params = dict(params)
        params.setdefault("properties", {})

    description = str(tool.get("description") or f"MCP 工具 {tool.get('name')}").strip()
    return {
        "type": "function",
        "function": {
            "name": fn_name,
            "description": f"[MCP:{server_name}] {description}",
            "parameters": params,
        },
    }


async def _get_client(cfg: dict) -> MCPClient:
    """取（必要时启动）该 server 的连接；正常路径下子进程只启动一次。"""
    client = _clients.get(cfg["name"])
    if client is not None and client.is_running:
        return client
    if client is not None:
        # 进程已死：回收后重建，避免复用僵尸连接
        await client.stop()

    client = MCPClient(
        command=cfg["command"],
        args=cfg.get("args"),
        name=cfg["name"],
        cwd=cfg.get("cwd"),
        env=cfg.get("env"),
        timeout=cfg.get("timeout") or DEFAULT_TIMEOUT,
    )
    await client.start()
    _clients[cfg["name"]] = client
    return client


async def list_openai_tools(refresh: bool = False) -> list[dict]:
    """把所有已启用 MCP server 的工具转换为 OpenAI tools 格式。

    单个 server 不可用时只跳过它并记录日志，不影响其它 server 与内置工具。
    """
    global _schemas, _loaded

    async with _lock:
        if _loaded and not refresh:
            return list(_schemas)

        schemas: list[dict] = []
        name_map: dict[str, tuple[str, str]] = {}
        configs: dict[str, dict] = {}
        used: set[str] = set()

        for cfg in load_server_configs():
            try:
                client = await _get_client(cfg)
                tools = await client.list_tools(refresh=refresh)
            except Exception as e:
                _log(f"MCP server {cfg['name']} 不可用，已跳过：{e}")
                continue

            server_name = cfg["name"]
            configs[server_name] = cfg
            for tool in tools:
                fn_name = _normalize_name(server_name, str(tool["name"]), used)
                name_map[fn_name] = (server_name, str(tool["name"]))
                schemas.append(_to_openai_schema(fn_name, server_name, tool))
            _log(f"MCP server {server_name} 提供 {len(tools)} 个工具")

        _schemas = schemas
        _configs.clear()
        _configs.update(configs)
        _name_map.clear()
        _name_map.update(name_map)
        _loaded = True
        return list(_schemas)


async def call_openai_tool(name: str, arguments: Optional[dict] = None) -> dict:
    """调用被规范化的 MCP 工具，返回 `{ok, text, raw}`。

    任何异常（未注册 / 进程不可用 / 超时 / 协议错误）都收敛为 `ok=False`，
    由调用方决定如何向 LLM 与用户降级。
    """
    if not _loaded:
        try:
            await list_openai_tools()
        except Exception as e:
            _log(f"初始化 MCP 工具列表失败：{e}")
            return {"ok": False, "text": f"MCP 不可用：{e}", "raw": {}}

    target = _name_map.get(name)
    if target is None:
        known = "、".join(_name_map) or "无"
        return {
            "ok": False,
            "text": f"未注册的 MCP 工具：{name}（当前可用：{known}）",
            "raw": {},
        }

    server_name, tool_name = target
    cfg = _configs.get(server_name)
    if cfg is None:
        return {"ok": False, "text": f"MCP server {server_name} 未启用或已下线", "raw": {}}

    try:
        client = await _get_client(cfg)
        result = await client.call_tool(tool_name, arguments or {})
    except MCPError as e:
        _log(f"{name} 调用失败：{e}")
        return {"ok": False, "text": f"MCP 工具 {name} 调用失败：{e}", "raw": {}}
    except Exception as e:
        _log(f"{name} 调用异常：{e}")
        return {"ok": False, "text": f"MCP 工具 {name} 调用异常：{e}", "raw": {}}

    text = str(result.get("text") or "")
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + f"\n…（内容已截断，原文 {len(text)} 字符）"
    if result.get("ok") and not text:
        text = f"MCP 工具 {name} 执行成功，但未返回文本内容。"

    return {"ok": bool(result.get("ok")), "text": text, "raw": result.get("raw") or {}}


def mcp_tool_names() -> list[str]:
    """已注册的 MCP 函数名（供调试 / 管理页展示）。"""
    return list(_name_map)


async def shutdown_all() -> None:
    """停止全部 MCP 子进程并清空注册表（应用关闭或测试收尾调用）。"""
    global _schemas, _loaded

    async with _lock:
        for server_name, client in list(_clients.items()):
            try:
                await client.stop()
            except Exception as e:
                _log(f"停止 MCP server {server_name} 失败：{e}")
        _clients.clear()
        _configs.clear()
        _name_map.clear()
        _schemas = []
        _loaded = False
