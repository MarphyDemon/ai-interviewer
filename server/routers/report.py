import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from server.database import get_session
from server.models import Report

router = APIRouter(prefix="/api/report", tags=["report"])


@router.get("/{interview_id}")
async def get_report(interview_id: int, session: Session = Depends(get_session)):
    report = session.exec(
        select(Report).where(Report.interview_id == interview_id)
    ).first()
    if not report:
        raise HTTPException(404, "Report not found")

    return {
        "id": report.id,
        "interviewId": report.interview_id,
        "totalScore": report.total_score,
        "dimensionScores": json.loads(report.dimension_scores) if report.dimension_scores else [],
        "summary": report.summary,
        "perQuestionReviews": json.loads(report.per_question_reviews) if report.per_question_reviews else [],
        "resumeReview": json.loads(report.resume_review) if report.resume_review else None,
        "jobFit": report.job_fit,
        "createdAt": report.created_at.isoformat() if report.created_at else None,
    }
