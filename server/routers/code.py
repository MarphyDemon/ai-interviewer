"""P3 代码与算法练习模块路由。

提供：
- 算法题列表/详情
- 代码即时运行（stdin 自定义）
- 提交判定（批量用例）
- AI 提示（基于题面 + 用户代码给思路引导，非直接给答案）
- 提交历史
- 流式 AI 对话（出题、评价、引导）
"""
import json
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from server.database import get_session
from server.models import AlgorithmProblem, CodeSubmission, User, LLMConfig
from server.services.auth_service import get_current_user
from server.services.judge_service import (
    LANGUAGE_TEMPLATES,
    SUPPORTED_LANGUAGES,
    judge,
    run_code,
)
from server.services.llm_service import llm_chat, llm_chat_stream

router = APIRouter(prefix="/api/code", tags=["code"])


# ---------- 题目 ----------

@router.get("/problems")
async def list_problems(
    difficulty: Optional[str] = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """算法题列表（支持按难度筛选）。"""
    stmt = select(AlgorithmProblem).where(AlgorithmProblem.is_public == True)  # noqa: E712
    if difficulty:
        stmt = stmt.where(AlgorithmProblem.difficulty == difficulty)
    stmt = stmt.order_by(AlgorithmProblem.id)
    rows = session.exec(stmt).all()
    return [
        {
            "id": p.id,
            "title": p.title,
            "difficulty": p.difficulty,
            "position": p.position,
            "tags": json.loads(p.tags) if p.tags else [],
        }
        for p in rows
    ]


@router.get("/problems/{problem_id}")
async def get_problem(
    problem_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """算法题详情（不含隐藏测试用例）。"""
    p = session.get(AlgorithmProblem, problem_id)
    if not p or not p.is_public:
        raise HTTPException(404, "题目不存在")
    return {
        "id": p.id,
        "title": p.title,
        "description": p.description,
        "difficulty": p.difficulty,
        "position": p.position,
        "tags": json.loads(p.tags) if p.tags else [],
        "examples": json.loads(p.examples) if p.examples else [],
        "timeLimitMs": p.time_limit_ms,
        "memoryLimitMb": p.memory_limit_mb,
    }


# ---------- 语言 ----------

@router.get("/languages")
async def list_languages(user: User = Depends(get_current_user)):
    """支持的语言列表 + 代码模板。"""
    return [
        {
            "id": lang,
            "label": _lang_label(lang),
            "template": LANGUAGE_TEMPLATES.get(lang, ""),
        }
        for lang in SUPPORTED_LANGUAGES
    ]


def _lang_label(lang: str) -> str:
    return {
        "python": "Python 3",
        "javascript": "JavaScript",
        "typescript": "TypeScript",
        "java": "Java",
        "cpp": "C++",
        "c": "C",
        "go": "Go",
        "rust": "Rust",
    }.get(lang, lang)


# ---------- 代码运行 ----------

class RunRequest(BaseModel):
    language: str
    code: str
    stdin: str = ""


@router.post("/run")
async def run_code_endpoint(
    req: RunRequest,
    user: User = Depends(get_current_user),
):
    """即时运行代码（不计入提交记录）。"""
    result = await run_code(req.language, req.code, stdin=req.stdin)
    if result.exit_code == -1 and result.stderr.startswith("不支持的语言"):
        raise HTTPException(400, result.stderr)
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exitCode": result.exit_code,
        "signal": result.signal,
        "durationMs": result.duration_ms,
        "compileError": result.compile_error,
    }


# ---------- 提交判定 ----------

class SubmitRequest(BaseModel):
    problemId: int
    language: str
    code: str


@router.post("/submit")
async def submit_code(
    req: SubmitRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """提交代码并判定全部测试用例。"""
    p = session.get(AlgorithmProblem, req.problemId)
    if not p:
        raise HTTPException(404, "题目不存在")

    test_cases = json.loads(p.test_cases) if p.test_cases else []
    result = await judge(test_cases, req.language, req.code)

    # 持久化提交记录
    sub = CodeSubmission(
        user_id=user.id,
        problem_id=req.problemId,
        language=req.language,
        code=req.code,
        status=result.status,
        stdout=result.stdout,
        stderr=result.stderr,
        pass_count=result.pass_count,
        total_count=result.total_count,
        duration_ms=result.duration_ms,
    )
    session.add(sub)
    session.commit()
    session.refresh(sub)

    return {
        "submissionId": sub.id,
        "status": result.status,
        "passCount": result.pass_count,
        "totalCount": result.total_count,
        "durationMs": result.duration_ms,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "compileError": result.compile_error,
        "cases": [
            {
                "passed": c.passed,
                "input": c.input,
                "expected": c.expected,
                "actual": c.actual,
                "stderr": c.stderr,
            }
            for c in result.cases
        ],
    }


# ---------- AI 提示 ----------

class HintRequest(BaseModel):
    problemId: int
    language: str
    code: str
    question: str = "请给我一些思路提示"


@router.post("/hint")
async def get_hint(
    req: HintRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """AI 思路提示：引导用户思考，不直接给完整答案。"""
    p = session.get(AlgorithmProblem, req.problemId)
    if not p:
        raise HTTPException(404, "题目不存在")

    messages = [
        {
            "role": "system",
            "content": (
                "你是一位算法教练。根据题目和用户的当前代码，给出**思路引导**而非完整答案。"
                "指出用户代码的问题、提示优化方向、解释关键概念。回复用 Markdown，简洁有重点。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"## 题目\n{p.title}\n\n{p.description}\n\n"
                f"## 语言\n{req.language}\n\n"
                f"## 我的代码\n```\n{req.code}\n```\n\n"
                f"## 我的问题\n{req.question}"
            ),
        },
    ]
    try:
        reply = await llm_chat(messages, session=session)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"AI 提示生成失败: {e}")
    return {"hint": reply}


# ---------- 提交历史 ----------

@router.get("/submissions")
async def list_submissions(
    problemId: Optional[int] = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """当前用户的提交历史。"""
    stmt = select(CodeSubmission).where(CodeSubmission.user_id == user.id)
    if problemId:
        stmt = stmt.where(CodeSubmission.problem_id == problemId)
    stmt = stmt.order_by(CodeSubmission.id.desc()).limit(50)
    rows = session.exec(stmt).all()
    return [
        {
            "id": s.id,
            "problemId": s.problem_id,
            "language": s.language,
            "status": s.status,
            "passCount": s.pass_count,
            "totalCount": s.total_count,
            "durationMs": s.duration_ms,
            "createdAt": s.created_at.isoformat(),
        }
        for s in rows
    ]


@router.get("/submissions/{sub_id}")
async def get_submission(
    sub_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """提交详情（含代码）。"""
    s = session.get(CodeSubmission, sub_id)
    if not s or s.user_id != user.id:
        raise HTTPException(404, "提交记录不存在")
    return {
        "id": s.id,
        "problemId": s.problem_id,
        "language": s.language,
        "code": s.code,
        "status": s.status,
        "stdout": s.stdout,
        "stderr": s.stderr,
        "passCount": s.pass_count,
        "totalCount": s.total_count,
        "durationMs": s.duration_ms,
        "createdAt": s.created_at.isoformat(),
    }


# ---------- 流式 AI 对话 ----------

class CodeChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class CodeChatRequest(BaseModel):
    message: str
    language: str = "python"
    code: str = ""
    history: list[CodeChatMessage] = []
    difficulty: str = "中等"
    position: str = "算法"


@router.post("/chat/stream")
async def code_chat_stream(
    req: CodeChatRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """流式算法陪练对话：AI 出题、引导、评价代码。"""

    system_prompt = (
        "你是一位算法面试教练。你的职责是帮助用户通过编程练习提升算法能力。\n\n"
        "## 你的能力\n"
        "1. **出题**：当用户说「出题」「来一道题」「开始」等时，生成一道编程题。"
        "题目需包含：标题、题目描述、输入输出说明、至少2个示例（含输入/输出/解释）、"
        "限制条件（时间/空间复杂度要求）。题目难度和岗位方向参考用户提供的 difficulty 和 position。\n"
        "2. **引导思路**：用户问思路时，给提示引导而非直接给完整代码。\n"
        "3. **评价代码**：用户提交代码后，分析代码的优缺点、时间复杂度、空间复杂度，给出改进建议。\n"
        "4. **回答问题**：回答用户关于算法、数据结构、编程语言等任何技术问题。\n\n"
        "## 回复风格\n"
        "- 使用 Markdown 格式，代码块用 ```language 标注\n"
        "- 出题时用清晰的标题层级，示例用表格或列表\n"
        "- 评价代码时先肯定好的地方，再指出可改进的点\n"
        "- 如果是中文提问就用中文回复，英文提问用英文回复\n\n"
        "## 当前上下文\n"
        f"- 用户选择的难度：{req.difficulty}\n"
        f"- 用户选择的岗位方向：{req.position}\n"
        f"- 用户当前使用的语言：{req.language}\n"
        f"- 用户当前代码：\n```\n{req.code or '(空)'}\n```"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for h in req.history:
        messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": req.message})

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for delta in llm_chat_stream(messages, session=session):
                yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except HTTPException as e:
            yield f"data: {json.dumps({'error': e.detail}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
