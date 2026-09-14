import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from server.database import get_session
from server.models import Interview, InterviewMessage, Report, Resume, User, AlgorithmProblem, CodeSubmission
from server.services.interview_service import (
    generate_first_question,
    process_answer,
    generate_report,
    save_message,
    pick_algorithm_problem,
    format_problem_for_interview,
)
from server.services.auth_service import get_current_user
from server.services.common import get_active_llm_config
from server.services.judge_service import judge
from server.services.interview_brain_service import create_interview_session
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
    """为数字人 SDK 签发面试专用 brain_config。

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
            response["problem"] = format_problem_for_interview(problem)

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
            response["nextQuestion"]["problem"] = format_problem_for_interview(next_problem)

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


@router.delete("/{interview_id}")
async def delete_interview(
    interview_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    interview = session.get(Interview, interview_id)
    if not interview or interview.user_id != user.id:
        raise HTTPException(404, "Interview not found")

    reports = session.exec(
        select(Report).where(Report.interview_id == interview_id)
    ).all()
    for r in reports:
        session.delete(r)

    messages = session.exec(
        select(InterviewMessage).where(InterviewMessage.interview_id == interview_id)
    ).all()
    for m in messages:
        session.delete(m)

    session.flush()
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

        reports = session.exec(
            select(Report).where(Report.interview_id == interview_id)
        ).all()
        for r in reports:
            session.delete(r)

        messages = session.exec(
            select(InterviewMessage).where(InterviewMessage.interview_id == interview_id)
        ).all()
        for m in messages:
            session.delete(m)

        session.flush()
        session.delete(interview)
        deleted += 1

    session.commit()
    return {"ok": True, "deleted": deleted}
