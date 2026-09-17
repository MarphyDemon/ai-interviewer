"""MCP 链路冒烟脚本。

用法（在仓库根目录执行，无需任何第三方依赖与网络）：
    python server/scripts/mcp_smoke.py

流程：
    list_openai_tools() → 断言包含 2 个工具 → 依次真实调用两个工具 → 打印结果
    → shutdown_all()

成功 exit 0，任一步失败 exit 1（便于 CI 判定）。
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

# 允许以脚本方式直接运行：把仓库根目录加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.services.mcp_service import (  # noqa: E402  （必须在 sys.path 处理之后导入）
    call_openai_tool,
    list_openai_tools,
    shutdown_all,
)

EXPECTED_TOOL_COUNT = 2
SEARCH_TOOL_SUFFIX = "search_question_bank"
PROFILE_TOOL_SUFFIX = "get_company_profile"


def _pick(names: list[str], suffix: str) -> Optional[str]:
    return next((n for n in names if n.endswith(suffix)), None)


async def main() -> int:
    exit_code = 1
    try:
        print("=" * 72)
        print("步骤 1/3  list_openai_tools()")
        print("=" * 72)
        tools = await list_openai_tools()
        names = [str(t.get("function", {}).get("name", "")) for t in tools]
        for tool in tools:
            fn = tool.get("function", {})
            print(f"- {fn.get('name')}: {str(fn.get('description', ''))[:70]}")

        if len(names) != EXPECTED_TOOL_COUNT:
            print(f"\n[FAIL] 期望 {EXPECTED_TOOL_COUNT} 个工具，实际 {len(names)} 个：{names}")
            return exit_code

        search_tool = _pick(names, SEARCH_TOOL_SUFFIX)
        profile_tool = _pick(names, PROFILE_TOOL_SUFFIX)
        if not search_tool or not profile_tool:
            print(f"\n[FAIL] 未找到预期工具（{SEARCH_TOOL_SUFFIX} / {PROFILE_TOOL_SUFFIX}）：{names}")
            return exit_code
        print(f"\n[PASS] 工具数量与命名符合预期：{names}")

        print()
        print("=" * 72)
        print("步骤 2/3  call_openai_tool() 真实调用两个工具")
        print("=" * 72)

        calls = [
            (search_tool, {"query": "缓存 一致性", "position": "后端", "limit": 2}),
            (profile_tool, {"company": "字节跳动"}),
        ]
        all_ok = True
        for name, arguments in calls:
            print(f"\n>>> {name}({arguments})")
            result = await call_openai_tool(name, arguments)
            print(f"ok={result['ok']}")
            print(result["text"])
            if not result["ok"]:
                print(f"\n[FAIL] 工具 {name} 调用失败")
                all_ok = False

        if not all_ok:
            return exit_code
        print()
        print("[PASS] 两个 MCP 工具均真实调用成功")
        exit_code = 0
    except Exception as e:
        print(f"\n[FAIL] 冒烟脚本异常：{type(e).__name__}: {e}")
        exit_code = 1
    finally:
        print()
        print("=" * 72)
        print("步骤 3/3  shutdown_all()")
        print("=" * 72)
        try:
            await shutdown_all()
            print("[PASS] 已回收全部 MCP 子进程")
        except Exception as e:
            print(f"[FAIL] shutdown_all 异常：{e}")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
