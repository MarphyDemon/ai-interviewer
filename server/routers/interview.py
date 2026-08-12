from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from server.database import get_session
from server.models import Interview, InterviewMessage, Report, Resume
from server.services.interview_service import (
    generate_first_question,
    process_answer,
    generate_report,
    save_message,
)
from server.services.common import get_or_create_user

router = APIRouter(prefix="/api/interview", tags=["interview"])


class StartRequest(BaseModel):
    position: str
    difficulty: str
    duration: int = 30
    style: str = "friendly"
    resumeId: int | None = None
    lang: str = "en"


class AnswerRequest(BaseModel):
    answer: str


@router.post("/start")
async def start_interview(req: StartRequest, session: Session = Depends(get_session)):
    user_id = get_or_create_user(session, "default")

    interview = Interview(
        user_id=user_id,
        resume_id=req.resumeId,
        position=req.position,
        difficulty=req.difficulty,
        duration=req.duration,
        style=req.style,
    )
    session.add(interview)
    session.commit()
    session.refresh(interview)

    resume = session.get(Resume, req.resumeId) if req.resumeId else None

    first = await generate_first_question(session, interview, resume, lang=req.lang)

    save_message(
        session, interview.id, "interviewer", first.get("content", ""),
        question_index=1, followup_level=0,
    )

    return {
        "interviewId": interview.id,
        "firstQuestion": {
            "action": first.get("action", "ask"),
            "content": first.get("content", ""),
            "reasoning": first.get("reasoning", ""),
        },
    }


@router.post("/{interview_id}/answer")
async def submit_answer(
    interview_id: int,
    req: AnswerRequest,
    session: Session = Depends(get_session),
):
    interview = session.get(Interview, interview_id)
    if not interview:
        raise HTTPException(404, "Interview not found")

    save_message(session, interview_id, "user", req.answer)

    result = await process_answer(session, interview, req.answer)

    save_message(
        session, interview_id, "interviewer", result.get("content", ""),
        question_index=0, followup_level=0,
    )

    if result.get("action") == "end":
        await generate_report(session, interview)

    return {
        "action": result.get("action", "next_question"),
        "content": result.get("content", ""),
        "reasoning": result.get("reasoning", ""),
    }


@router.post("/{interview_id}/end")
async def end_interview(interview_id: int, session: Session = Depends(get_session)):
    interview = session.get(Interview, interview_id)
    if not interview:
        raise HTTPException(404, "Interview not found")
    await generate_report(session, interview)
    return {"ok": True}


@router.get("/history")
async def get_history(session: Session = Depends(get_session)):
    interviews = session.exec(select(Interview)).all()
    return [
        {
            "id": i.id,
            "position": i.position,
            "difficulty": i.difficulty,
            "duration": i.duration,
            "style": i.style,
            "status": i.status,
            "startedAt": i.started_at.isoformat() if i.started_at else None,
            "endedAt": i.ended_at.isoformat() if i.ended_at else None,
        }
        for i in interviews
    ]


@router.delete("/{interview_id}")
async def delete_interview(interview_id: int, session: Session = Depends(get_session)):
    interview = session.get(Interview, interview_id)
    if not interview:
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

    session.delete(interview)
    session.commit()
    return {"ok": True}


class BatchDeleteRequest(BaseModel):
    ids: list[int]


@router.post("/batch-delete")
async def batch_delete_interviews(
    req: BatchDeleteRequest,
    session: Session = Depends(get_session),
):
    deleted = 0
    for interview_id in req.ids:
        interview = session.get(Interview, interview_id)
        if not interview:
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

        session.delete(interview)
        deleted += 1

    session.commit()
    return {"ok": True, "deleted": deleted}
