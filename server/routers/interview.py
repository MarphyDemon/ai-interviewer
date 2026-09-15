import json
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete
from sqlmodel import Session, SQLModel, select
from server.database import get_session
from server.models import (
    Interview,
    Resume,
    User,
    AlgorithmProblem,
    CodeSubmission,
)
from server.services.interview_service import (
    generate_first_question,
    process_answer,
    generate_report,
    save_message,
    pick_algorithm_problem,
    format_problem_for_interview,
)
from server.services.auth_service import get_current_user, verify_user_token
from server.services.common import get_active_llm_config
from server.services.judge_service import judge
from server.services.interview_brain_service import create_interview_session
from server.services.interview_event_bus import publish, subscribe
from server.config import settings
from server.models import JobDescription

router = APIRouter(prefix="/api/interview", tags=["interview"])


class StartRequest(BaseModel):
    position: str
    difficulty: str
    duration: int = 30
    style: str = "friendly"
    resumeId: int | None = None
    jdId: int | None = None
    lang: str = "en"


class AnswerRequest(BaseModel):
    answer: str


@router.post("/start")
async def start_interview(
    req: StartRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    interview = Interview(
        user_id=user.id,
        resume_id=req.resumeId,
        jd_id=req.jdId,
        position=req.position,
        difficulty=req.difficulty,
        duration=req.duration,
        style=req.style,
    )
    session.add(interview)
    session.commit()
    session.refresh(interview)

    resume = session.get(Resume, req.resumeId) if req.resumeId else None
    jd = session.get(JobDescription, req.jdId) if req.jdId else None

    first = await generate_first_question(session, interview, resume, jd=jd, lang=req.lang)

    save_message(
        session, interview.id, "interviewer", first.get("content", ""),
        question_index=1, followup_level=0,
    )

    response = {
        "interviewId": interview.id,
        "firstQuestion": {
            "action": first.get("action", "ask"),
            "content": first.get("content", ""),
            "reasoning": first.get("reasoning", ""),
        },
    }

    # 如果首题是算法题，附带题目详情
    if first.get("action") == "algorithm":
        problem = pick_algorithm_problem(session, interview.difficulty)
        if problem:
            response["firstQuestion"]["problem"] = format_problem_for_interview(problem)

    return response


@router.post("/{interview_id}/avatar-session")
async def create_avatar_session(
    interview_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """为具身交互智能体 SDK 签发面试专用 brain_config。

    返回的 api_key 是**面试会话 token**：SDK 携带它请求 brain proxy 时会命中
    interview_brain_service（面试官大脑），而不是聊天链路（学习导师）。

    - 代理模式（avatar_proxy_base_url 已配置）：返回代理 URL + 面试 token
    - 直连模式（未配置）：返回真实 LLM 配置，便于本地开发
    """
    interview = session.get(Interview, interview_id)
    if not interview or interview.user_id != user.id:
        raise HTTPException(404, "面试不存在")

    cfg = get_active_llm_config(session)

    if settings.avatar_proxy_base_url:
        try:
            token_str = create_interview_session(session, user.id, interview_id)
        except ValueError as e:
            raise HTTPException(404, str(e))

        proxy_base = settings.avatar_proxy_base_url.rstrip("/") + "/api/avatar/brain-proxy/v1"
        return {
            "provider": "openai",
            "model": cfg.model,
            "api_key": token_str,
            "base_url": proxy_base,
            "extra_body": {"temperature": 0.7},
        }

    # 直连模式：本地开发友好
    provider = "deepseek"
    base_url = cfg.base_url
    if "volces" in base_url or "ark" in base_url:
        provider = "volces"
    elif "siliconflow" in base_url:
        provider = "siliconflow"
    elif "openrouter" in base_url:
        provider = "openrouter"
    elif "together" in base_url:
        provider = "together"

    return {
        "provider": provider,
        "model": cfg.model,
        "api_key": cfg.api_key,
        "base_url": cfg.base_url,
        "extra_body": {"temperature": 0.7},
    }


@router.get("/{interview_id}/events")
async def interview_events(
    interview_id: int,
    token: str = Query(..., description="用户登录 token（EventSource 无法自定义请求头）"),
    session: Session = Depends(get_session),
):
    """面试事件流（SSE 旁路）。

    推送 brain 流水线中的结构化事件：tool_start / tool_result / widget / emotion / metrics。
    这些事件**不能**混进 brain 代理的 SSE 正文字段，否则会被具身交互智能体当成播报文本念出来，
    因此单独开一条通道。

    浏览器 EventSource 不支持自定义请求头，故 token 走查询参数。
    """
    user_id = verify_user_token(token)
    if user_id is None:
        raise HTTPException(401, "无效的登录凭证")

    interview = session.get(Interview, interview_id)
    if not interview or interview.user_id != user_id:
        raise HTTPException(404, "面试不存在")

    async def event_stream():
        # 首帧注释：立即建立连接，避免被反向代理缓冲
        yield ": connected\n\n"
        sub = subscribe(interview_id)
        try:
            while True:
                event = await sub.get(20)
                if event is None:
                    yield ": keep-alive\n\n"
                    continue
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            sub.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{interview_id}/answer")
async def submit_answer(
    interview_id: int,
    req: AnswerRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    interview = session.get(Interview, interview_id)
    if not interview or interview.user_id != user.id:
        raise HTTPException(404, "Interview not found")

    save_message(session, interview_id, "user", req.answer)

    result = await process_answer(session, interview, req.answer)

    save_message(
        session, interview_id, "interviewer", result.get("content", ""),
        question_index=0, followup_level=0,
    )

    if result.get("action") == "end":
        await generate_report(session, interview)

    response = {
        "action": result.get("action", "next_question"),
        "content": result.get("content", ""),
        "reasoning": result.get("reasoning", ""),
    }

    # 如果下一题是算法题，附带题目详情
    if result.get("action") == "algorithm":
        problem = pick_algorithm_problem(session, interview.difficulty)
        if problem:
            formatted = format_problem_for_interview(problem)
            response["problem"] = formatted
            # 文字路径不走 brain 管线，这里主动补发 widget 事件，
            # 让算法题卡片在两条路径下表现一致
            publish(
                interview_id,
                {
                    "type": "widget",
                    "payload": {
                        "type": "question_card",
                        "id": f"problem-{problem.id}",
                        "data": formatted,
                        "ttl": 600000,
                    },
                },
            )

    return response


@router.post("/{interview_id}/end")
async def end_interview(
    interview_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    interview = session.get(Interview, interview_id)
    if not interview or interview.user_id != user.id:
        raise HTTPException(404, "Interview not found")
    await generate_report(session, interview)
    return {"ok": True}


class InterviewCodeRequest(BaseModel):
    problemId: int
    language: str
    code: str


@router.post("/{interview_id}/submit-code")
async def submit_interview_code(
    interview_id: int,
    req: InterviewCodeRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """面试中提交算法题代码：判定 + 保存为答题记录 + 返回下一题。"""
    interview = session.get(Interview, interview_id)
    if not interview or interview.user_id != user.id:
        raise HTTPException(404, "Interview not found")

    problem = session.get(AlgorithmProblem, req.problemId)
    if not problem:
        raise HTTPException(404, "题目不存在")

    # 判题
    test_cases = json.loads(problem.test_cases) if problem.test_cases else []
    result = await judge(test_cases, req.language, req.code)

    # 保存提交记录
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

    # 将代码判定结果作为面试回答保存
    answer_summary = f"[算法题: {problem.title}] 语言: {req.language}, 结果: {result.status} ({result.pass_count}/{result.total_count})"
    save_message(session, interview_id, "user", answer_summary)

    # 生成下一题
    next_result = await process_answer(session, interview, answer_summary)
    save_message(
        session, interview_id, "interviewer", next_result.get("content", ""),
        question_index=0, followup_level=0,
    )

    if next_result.get("action") == "end":
        await generate_report(session, interview)

    response = {
        "judgeResult": {
            "status": result.status,
            "passCount": result.pass_count,
            "totalCount": result.total_count,
            "durationMs": result.duration_ms,
            "compileError": result.compile_error,
            "cases": [
                {
                    "passed": c.passed,
                    "input": c.input,
                    "expected": c.expected,
                    "actual": c.actual,
                }
                for c in result.cases
            ],
        },
        "nextQuestion": {
            "action": next_result.get("action", "next_question"),
            "content": next_result.get("content", ""),
            "reasoning": next_result.get("reasoning", ""),
        },
    }

    # 如果下一题又是算法题，附带题目详情
    if next_result.get("action") == "algorithm":
        next_problem = pick_algorithm_problem(session, interview.difficulty)
        if next_problem:
            next_formatted = format_problem_for_interview(next_problem)
            response["nextQuestion"]["problem"] = next_formatted
            publish(
                interview_id,
                {
                    "type": "widget",
                    "payload": {
                        "type": "question_card",
                        "id": f"problem-{next_problem.id}",
                        "data": next_formatted,
                        "ttl": 600000,
                    },
                },
            )

    # 判题结果同样补发 widget 事件
    publish(
        interview_id,
        {
            "type": "widget",
            "payload": {
                "type": "judge_result",
                "id": f"judge-{req.problemId}",
                "data": {
                    "title": problem.title,
                    "status": result.status,
                    "passCount": result.pass_count,
                    "totalCount": result.total_count,
                    "durationMs": result.duration_ms,
                    "compileError": result.compile_error,
                    "cases": [
                        {
                            "passed": c.passed,
                            "input": c.input,
                            "expected": c.expected,
                            "actual": c.actual,
                        }
                        for c in result.cases
                    ],
                },
            },
        },
    )

    session.commit()
    return response


@router.get("/history")
async def get_history(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    interviews = session.exec(select(Interview).where(Interview.user_id == user.id)).all()
    return [
        _format_interview(i)
        for i in interviews
    ]


@router.get("/{interview_id}")
async def get_interview(
    interview_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """获取单场面试详情。"""
    interview = session.get(Interview, interview_id)
    if not interview or interview.user_id != user.id:
        raise HTTPException(404, "面试不存在")
    return _format_interview(interview)


def _format_interview(i: Interview) -> dict:
    return {
        "id": i.id,
        "position": i.position,
        "difficulty": i.difficulty,
        "duration": i.duration,
        "style": i.style,
        "status": i.status,
        "startedAt": i.started_at.isoformat() if i.started_at else None,
        "endedAt": i.ended_at.isoformat() if i.ended_at else None,
    }


def _purge_interview_children(session: Session, interview_id: int) -> None:
    """删除所有以 ForeignKey 直接指向 interview 的子表记录。

    引用表通过 SQLModel.metadata **自动发现**，而不是维护硬编码清单：
    今后新增任何直接引用 interview 的表都会被自动清理，不会再出现"加了表忘了改删除逻辑"。

    背景：漏掉任何一张引用表，在 PostgreSQL 上都会抛 ForeignKeyViolation
    （SQLite 默认不校验外键，本地测不出来），表现为「删除面试」接口 500。

    局限：只处理直接子表。若将来出现引用子表的"孙表"，需要另按依赖深度处理。
    """
    root = Interview.__table__
    for table in SQLModel.metadata.tables.values():
        if table is root:
            continue
        fk_columns = [
            col
            for col in table.columns
            for fk in col.foreign_keys
            if fk.column.table is root
        ]
        if not fk_columns:
            continue
        session.execute(
            sa_delete(table).where(*[col == interview_id for col in fk_columns])
        )
    # 子表已通过 Core DELETE 立即落库，这里再 flush 确保父表删除排在其后
    session.flush()


@router.delete("/{interview_id}")
async def delete_interview(
    interview_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    interview = session.get(Interview, interview_id)
    if not interview or interview.user_id != user.id:
        raise HTTPException(404, "Interview not found")

    _purge_interview_children(session, interview_id)
    session.delete(interview)
    session.commit()
    return {"ok": True}


class BatchDeleteRequest(BaseModel):
    ids: list[int]


@router.post("/batch-delete")
async def batch_delete_interviews(
    req: BatchDeleteRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    deleted = 0
    for interview_id in req.ids:
        interview = session.get(Interview, interview_id)
        if not interview or interview.user_id != user.id:
            continue

        _purge_interview_children(session, interview_id)
        session.delete(interview)
        deleted += 1

    session.commit()
    return {"ok": True, "deleted": deleted}
