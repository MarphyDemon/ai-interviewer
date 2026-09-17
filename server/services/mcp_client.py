"""极简 MCP（Model Context Protocol）客户端 —— 子进程 stdio + 单行 JSON-RPC 2.0。

为什么不用官方 `mcp` / `fastmcp` 包：
本项目坚持「未验证的依赖不引入」，而官方 SDK 无法在当前环境安装验证；
而 MCP 的 stdio 传输本身只是「一行一个 JSON-RPC 消息」，标准库即可实现并自测。

协议要点（对齐 MCP 2024-11-05 规范的 stdio 传输）：
- 传输：子进程 stdin/stdout，每条消息为一行 JSON（UTF-8），行内不含换行
- 握手：`initialize`（protocolVersion / capabilities / clientInfo）
        → 收到 result 后发通知 `notifications/initialized`
- 发现：`tools/list` → `result.tools[]`（name / description / inputSchema）
- 调用：`tools/call` → `result.content[]`（如 {type:"text", text}）与 `result.isError`
- 服务端 stderr 不是协议通道，由后台任务读取后转写到本进程 stderr

用法：
    async with MCPClient(sys.executable, ["-m", "server.mcp_servers.sample_interview_server"]) as client:
        tools = await client.list_tools()
        result = await client.call_tool("get_company_profile", {"company": "字节跳动"})
"""

import asyncio
import json
import os
import sys
from typing import Optional, Sequence

PROTOCOL_VERSION = "2024-11-05"
CLIENT_NAME = "ai-interviewer"
CLIENT_VERSION = "0.1.0"
DEFAULT_TIMEOUT = 20.0
_STOP_TIMEOUT = 5.0


class MCPError(RuntimeError):
    """MCP 客户端的可读异常：启动失败、进程退出、超时、协议错误。"""


def _log(message: str) -> None:
    """客户端诊断日志统一写 stderr，避免污染调用方的 stdout。"""
    print(f"[MCP] {message}", file=sys.stderr)


class MCPClient:
    """单个 MCP server 的连接（一个子进程 + 一条 JSON-RPC 会话）。"""

    def __init__(
        self,
        command: str,
        args: Optional[Sequence[str]] = None,
        name: str = "",
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.name = name or os.path.splitext(os.path.basename(str(command)))[0]
        self.timeout = float(timeout)
        self._command = str(command)
        self._args = [str(a) for a in (args or [])]
        self._cwd = str(cwd) if cwd else None
        self._env = dict(env or {})
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._pending: dict[int, asyncio.Future] = {}
        self._next_id = 0
        self._reader_task: Optional[asyncio.Task] = None
        self._stderr_task: Optional[asyncio.Task] = None
        self._write_lock = asyncio.Lock()
        self._tools: list[dict] = []
        self._server_info: dict = {}

    # ---------- 生命周期 ----------

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    @property
    def server_info(self) -> dict:
        return dict(self._server_info)

    async def start(self) -> "MCPClient":
        """启动子进程并完成 initialize 握手。可重复调用（已在运行则直接返回）。"""
        if self.is_running:
            return self

        base_env = os.environ.copy()
        base_env.update({k: str(v) for k, v in self._env.items()})
        # Windows 下子进程默认按 GBK 编码读写，必须显式指定 UTF-8，否则中文协议帧会乱码
        base_env.setdefault("PYTHONIOENCODING", "utf-8")
        base_env.setdefault("PYTHONUNBUFFERED", "1")

        try:
            self._proc = await asyncio.create_subprocess_exec(
                self._command,
                *self._args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._cwd,
                env=base_env,
            )
        except NotImplementedError as e:
            raise MCPError(
                f"MCP server {self.name} 启动失败：当前事件循环不支持子进程"
                f"（Windows 下请使用默认的 ProactorEventLoop）：{e}"
            ) from e
        except FileNotFoundError as e:
            raise MCPError(f"MCP server {self.name} 启动失败：命令不存在 {self._command}") from e
        except Exception as e:
            raise MCPError(f"MCP server {self.name} 启动失败：{e}") from e

        self._reader_task = asyncio.create_task(self._read_loop())
        self._stderr_task = asyncio.create_task(self._stderr_loop())

        try:
            self._server_info = await self._request(
                "initialize",
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
                },
            )
            await self._notify("notifications/initialized", {})
        except Exception:
            await self.stop()
            raise
        return self

    async def stop(self) -> None:
        """关闭 stdin、等待子进程退出，并回收后台任务。幂等。"""
        proc, self._proc = self._proc, None
        for task in (self._reader_task, self._stderr_task):
            if task is not None:
                task.cancel()
        self._reader_task = None
        self._stderr_task = None
        self._fail_pending(MCPError(f"MCP server {self.name} 已停止"))

        if proc is None:
            return
        try:
            if proc.stdin is not None and not proc.stdin.is_closing():
                proc.stdin.close()
            await asyncio.wait_for(proc.wait(), timeout=_STOP_TIMEOUT)
        except asyncio.TimeoutError:
            _log(f"{self.name} 未在 {_STOP_TIMEOUT:.0f}s 内退出，强制结束")
            try:
                proc.kill()
                await proc.wait()
            except Exception as e:
                _log(f"{self.name} 强制结束失败：{e}")
        except Exception as e:
            _log(f"{self.name} 停止时异常：{e}")

    async def __aenter__(self) -> "MCPClient":
        return await self.start()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop()

    # ---------- 协议能力 ----------

    async def list_tools(self, refresh: bool = False) -> list[dict]:
        """tools/list → 每项含 name / description / inputSchema。"""
        if self._tools and not refresh:
            return self._tools
        result = await self._request("tools/list", {})
        tools = result.get("tools")
        if not isinstance(tools, list):
            raise MCPError(f"MCP server {self.name} 的 tools/list 返回格式非法：{str(result)[:200]}")
        self._tools = [t for t in tools if isinstance(t, dict) and t.get("name")]
        return self._tools

    async def call_tool(self, name: str, arguments: Optional[dict] = None) -> dict:
        """tools/call → 把 result.content[] 中的 text 片段合并到 `text` 字段。"""
        result = await self._request("tools/call", {"name": name, "arguments": arguments or {}})
        raw_content = result.get("content")
        contents = raw_content if isinstance(raw_content, list) else []
        texts = [
            str(item.get("text", ""))
            for item in contents
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        is_error = bool(result.get("isError"))
        text = "\n".join(t for t in texts if t)
        if is_error and not text:
            text = "MCP 工具返回了错误，但未提供文本原因。"
        return {
            "ok": not is_error,
            "text": text,
            "isError": is_error,
            "content": contents,
            "raw": result,
        }

    async def ping(self) -> bool:
        """协议存活探测（失败不抛出，由调用方决定如何处理）。"""
        try:
            await self._request("ping", {})
            return True
        except Exception as e:
            _log(f"{self.name} ping 失败：{e}")
            return False

    # ---------- 内部：收发 ----------

    async def _request(self, method: str, params: Optional[dict]) -> dict:
        if not self.is_running:
            raise MCPError(f"MCP server {self.name} 未启动或已退出，无法调用 {method}")

        self._next_id += 1
        req_id = self._next_id
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[req_id] = future

        await self._send({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}})

        try:
            message = await asyncio.wait_for(future, timeout=self.timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise MCPError(
                f"MCP server {self.name} 请求 {method} 超时（>{self.timeout:.0f}s）"
            ) from None

        error = message.get("error")
        if error:
            raise MCPError(
                f"MCP server {self.name} 请求 {method} 返回错误 "
                f"{error.get('code')}: {error.get('message')}"
            )
        result = message.get("result")
        return result if isinstance(result, dict) else {}

    async def _notify(self, method: str, params: Optional[dict]) -> None:
        await self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    async def _send(self, payload: dict) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            raise MCPError(f"MCP server {self.name} 不可写：进程未启动")
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        data = line.encode("utf-8")
        async with self._write_lock:
            try:
                proc.stdin.write(data)
                await proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError) as e:
                raise MCPError(f"MCP server {self.name} 写入失败（进程可能已退出）：{e}") from e

    async def _read_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                try:
                    message = json.loads(text)
                except json.JSONDecodeError:
                    _log(f"{self.name} 输出非 JSON（已忽略）：{text[:200]}")
                    continue
                if isinstance(message, dict):
                    self._dispatch(message)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            _log(f"{self.name} 读取 stdout 失败：{e}")
        finally:
            self._fail_pending(MCPError(f"MCP server {self.name} 的 stdout 已关闭（进程退出）"))

    async def _stderr_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stderr is None:
            return
        try:
            while True:
                line = await proc.stderr.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    _log(f"{self.name}:stderr {text}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            _log(f"{self.name} 读取 stderr 失败：{e}")

    def _dispatch(self, message: dict) -> None:
        msg_id = message.get("id")
        if msg_id is not None and ("result" in message or "error" in message):
            future = self._pending.pop(msg_id, None)
            if future is not None and not future.done():
                future.set_result(message)
            return

        method = message.get("method")
        if method and msg_id is not None:
            # 服务端反向请求（如 sampling）本客户端不支持，回标准错误避免对方挂起
            asyncio.create_task(
                self._send(
                    {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32601, "message": f"客户端未实现方法：{method}"},
                    }
                )
            )
            return
        if method:
            _log(f"{self.name} 收到通知 {method}（忽略）")

    def _fail_pending(self, exc: Exception) -> None:
        pending, self._pending = self._pending, {}
        for future in pending.values():
            if not future.done():
                future.set_exception(exc)
