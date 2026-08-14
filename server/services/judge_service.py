"""代码判题服务：基于 Judge0 CE 公共 API（https://ce.judge0.com）。

设计说明：
- Judge0 CE 是开源在线判题引擎，ce.judge0.com 提供公共实例，免鉴权。
- 本服务封装 Judge0 调用，提供 run_code（单次执行）与 judge（批量用例判定）两个核心能力。
- 使用 wait=true 同步等待执行结果，简化调用流程。
- 判题采用"逐用例执行 + 标准输出精确匹配"，MVP 不支持特判（SPJ）。

替代方案（如需更高可靠性/无速率限制）：
  自托管 Piston：docker run -d -p 2000:2000 ghcr.io/engineer-man/piston
  然后将 JUDGE0_ENDPOINT 改为 http://localhost:2000/api/v2/execute
"""
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

# Judge0 CE 公共实例（免鉴权，有速率限制）
JUDGE0_ENDPOINT = "https://ce.judge0.com/submissions"
JUDGE0_CPU_TIME_LIMIT = 5  # 秒
JUDGE0_MEMORY_LIMIT = 256  # MB

# 前端友好名 -> Judge0 language_id
LANGUAGE_MAP: dict[str, int] = {
    "python": 71,  # Python 3
    "javascript": 63,  # JavaScript (Node.js)
    "typescript": 74,  # TypeScript
    "java": 62,  # Java (OpenJDK)
    "cpp": 54,  # C++ (GCC 9.2.0)
    "c": 50,  # C (GCC 9.2.0)
    "go": 60,  # Go
    "rust": 73,  # Rust
}

SUPPORTED_LANGUAGES = list(LANGUAGE_MAP.keys())

# Judge0 status.id -> 含义
# 1=In Queue, 2=Processing, 3=Accepted, 4=Wrong Answer,
# 5=TLE, 6=Compilation Error, 7-13=Runtime Error, 14=Execution Error


@dataclass
class RunResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    signal: Optional[str] = None
    duration_ms: int = 0
    compile_error: str = ""


@dataclass
class CaseResult:
    passed: bool
    input: str
    expected: str
    actual: str
    stderr: str = ""


@dataclass
class JudgeResult:
    status: str
    pass_count: int = 0
    total_count: int = 0
    duration_ms: int = 0
    stdout: str = ""
    stderr: str = ""
    compile_error: str = ""
    cases: list[CaseResult] = field(default_factory=list)


async def _submit(source_code: str, language: str, stdin: str = "", expected_output: str = "") -> dict:
    """提交到 Judge0 并同步等待结果。"""
    lang_id = LANGUAGE_MAP.get(language)
    if lang_id is None:
        return {"error": f"不支持的语言: {language}"}

    payload = {
        "source_code": source_code,
        "language_id": lang_id,
        "stdin": stdin,
        "cpu_time_limit": JUDGE0_CPU_TIME_LIMIT,
        "memory_limit": JUDGE0_MEMORY_LIMIT * 1024,  # Judge0 用 KB
    }
    if expected_output:
        payload["expected_output"] = expected_output

    params = {"base64_encoded": "false", "wait": "true"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(JUDGE0_ENDPOINT, json=payload, params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        return {"error": "Judge0 请求超时", "status": {"id": 14, "description": "Timeout"}}
    except httpx.HTTPStatusError as e:
        return {"error": f"Judge0 HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"error": f"Judge0 调用异常: {e}"}


def _parse_status(data: dict) -> tuple[str, str, str]:
    """解析 Judge0 响应，返回 (status_str, stdout, stderr_or_compile_error)。"""
    if "error" in data:
        return "error", "", data["error"]

    status_id = data.get("status", {}).get("id", 0)
    stdout = data.get("stdout") or ""
    stderr = data.get("stderr") or ""
    compile_output = data.get("compile_output") or ""

    # 编译错误
    if status_id == 6:
        return "compile_error", stdout, compile_output

    # 运行时错误
    if status_id in (7, 8, 9, 10, 11, 12, 13):
        return "runtime_error", stdout, stderr

    # 超时
    if status_id == 5:
        return "timeout", stdout, "执行超时"

    # 执行错误
    if status_id == 14:
        return "error", stdout, stderr or data.get("message", "执行错误")

    # Accepted 或 Wrong Answer 由调用方比较输出决定
    return "ok", stdout, stderr


async def run_code(language: str, code: str, stdin: str = "") -> RunResult:
    """调用 Judge0 执行单段代码，返回标准化结果。"""
    if language not in LANGUAGE_MAP:
        return RunResult(stderr=f"不支持的语言: {language}", exit_code=-1)

    start = time.time()
    data = await _submit(code, language, stdin=stdin)
    duration_ms = int((time.time() - start) * 1000)

    status, stdout, err = _parse_status(data)
    if status == "error":
        return RunResult(stderr=err, exit_code=-1, duration_ms=duration_ms)
    if status == "compile_error":
        return RunResult(stdout=stdout, stderr="", compile_error=err, exit_code=1, duration_ms=duration_ms)
    if status == "timeout":
        return RunResult(stdout=stdout, stderr=err, exit_code=-1, signal="TIMEOUT", duration_ms=duration_ms)

    exit_code = 0 if status == "ok" else 1
    return RunResult(
        stdout=stdout,
        stderr=err if status == "runtime_error" else "",
        exit_code=exit_code,
        duration_ms=duration_ms,
    )


async def judge(
    test_cases: list[dict],
    language: str,
    code: str,
) -> JudgeResult:
    """批量执行测试用例并判定通过情况。

    test_cases: [{"input": "...", "expected": "..."}]
    判定逻辑：标准输出精确匹配（去除首尾空白后比较）。
    """
    total = len(test_cases)
    if total == 0:
        return JudgeResult(status="error", stderr="无测试用例")

    # 先跑第一个用例，检测编译错误
    first = test_cases[0]
    first_data = await _submit(code, language, stdin=first.get("input", ""))
    status, stdout, err = _parse_status(first_data)

    if status == "compile_error":
        return JudgeResult(
            status="compile_error",
            total_count=total,
            compile_error=err,
        )
    if status == "error":
        return JudgeResult(status="error", total_count=total, stderr=err)

    cases: list[CaseResult] = []
    pass_count = 0
    total_duration = 0

    # 第一个用例结果
    expected = (first.get("expected") or "").strip()
    actual = (stdout or "").strip()
    if status == "timeout":
        cases.append(CaseResult(False, first.get("input", ""), expected, actual, "超时"))
    else:
        ok = actual == expected
        cases.append(CaseResult(ok, first.get("input", ""), expected, actual, err if status == "runtime_error" else ""))
        if ok:
            pass_count += 1

    # 后续用例
    for tc in test_cases[1:]:
        data = await _submit(code, language, stdin=tc.get("input", ""))
        s, out, e = _parse_status(data)
        exp = (tc.get("expected") or "").strip()
        act = (out or "").strip()
        if s == "timeout":
            cases.append(CaseResult(False, tc.get("input", ""), exp, act, "超时"))
        elif s == "compile_error":
            # 编译错误应在第一次就检测到，这里防御性处理
            return JudgeResult(status="compile_error", total_count=total, compile_error=e)
        else:
            ok = act == exp
            cases.append(CaseResult(ok, tc.get("input", ""), exp, act, e if s == "runtime_error" else ""))
            if ok:
                pass_count += 1

    # 综合状态
    if pass_count == total:
        final_status = "accepted"
    else:
        final_status = "wrong_answer"
        for c in cases:
            if not c.passed:
                if "超时" in c.stderr:
                    final_status = "timeout"
                elif c.stderr:
                    final_status = "runtime_error"
                break

    last_case = cases[-1] if cases else None
    return JudgeResult(
        status=final_status,
        pass_count=pass_count,
        total_count=total,
        duration_ms=total_duration,
        stdout=last_case.actual if last_case else "",
        stderr=last_case.stderr if last_case else "",
        cases=cases,
    )


# ---------- 语言代码模板（前端新建文件时填充） ----------

LANGUAGE_TEMPLATES: dict[str, str] = {
    "python": "# Python 3\ndef main():\n    import sys\n    data = sys.stdin.read().split()\n    print(data)\n\nif __name__ == '__main__':\n    main()\n",
    "javascript": "// JavaScript (Node.js)\nconst main = () => {\n  let input = require('fs').readFileSync('/dev/stdin', 'utf8');\n  console.log(input.trim().split(/\\s+/));\n};\nmain();\n",
    "typescript": "// TypeScript\nconst main = () => {\n  let input = require('fs').readFileSync('/dev/stdin', 'utf8');\n  console.log(input.trim().split(/\\s+/));\n};\nmain();\n",
    "java": "// Java\nimport java.util.*;\npublic class Main {\n    public static void main(String[] args) {\n        Scanner sc = new Scanner(System.in);\n        System.out.println(sc.nextLine());\n    }\n}\n",
    "cpp": "// C++\n#include <bits/stdc++.h>\nusing namespace std;\nint main() {\n    string s;\n    cin >> s;\n    cout << s << endl;\n    return 0;\n}\n",
    "c": "// C\n#include <stdio.h>\nint main() {\n    char s[100];\n    scanf(\"%s\", s);\n    printf(\"%s\\n\", s);\n    return 0;\n}\n",
    "go": "// Go\npackage main\nimport \"fmt\"\nfunc main() {\n    var s string\n    fmt.Scan(&s)\n    fmt.Println(s)\n}\n",
    "rust": "// Rust\nuse std::io::{self, BufRead};\nfn main() {\n    let stdin = io::stdin();\n    for line in stdin.lock().lines() {\n        println!(\"{}\", line.unwrap());\n    }\n}\n",
}
