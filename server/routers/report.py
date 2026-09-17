import json
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
import io
from server.database import get_session
from server.models import Report, Interview, User
from server.services.auth_service import get_current_user
from server.services import org_service

router = APIRouter(prefix="/api/report", tags=["report"])

# 分享链接默认有效期
SHARE_DEFAULT_DAYS = 7
# base62 字母表
_BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _generate_share_token(length: int = 10) -> str:
    """生成 base62 短码"""
    return "".join(secrets.choice(_BASE62) for _ in range(length))


def _format_report(report: Report) -> dict:
    return {
        "id": report.id,
        "interviewId": report.interview_id,
        "totalScore": report.total_score,
        "dimensionScores": json.loads(report.dimension_scores) if report.dimension_scores else [],
        "summary": report.summary,
        "perQuestionReviews": json.loads(report.per_question_reviews) if report.per_question_reviews else [],
        "resumeReview": json.loads(report.resume_review) if report.resume_review else None,
        "jobFit": report.job_fit,
        "matchScore": report.match_score,
        "matchBreakdown": json.loads(report.match_breakdown) if report.match_breakdown else [],
        "createdAt": report.created_at.isoformat() if report.created_at else None,
    }


@router.get("/{interview_id}")
async def get_report(interview_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    report = session.exec(
        select(Report).where(Report.interview_id == interview_id)
    ).first()
    if not report:
        raise HTTPException(404, "Report not found")
    interview = session.get(Interview, report.interview_id)
    # 本人 / 企业组织成员（HR 查看候选人）/ admin 均可读
    if not org_service.can_view_interview(session, user, interview):
        raise HTTPException(404, "Report not found")
    return _format_report(report)


@router.get("/{interview_id}/pdf")
async def export_report_pdf(interview_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    report = session.exec(
        select(Report).where(Report.interview_id == interview_id)
    ).first()
    if not report:
        raise HTTPException(404, "Report not found")

    interview = session.get(Interview, report.interview_id)
    if not org_service.can_view_interview(session, user, interview):
        raise HTTPException(404, "Report not found")

    report_data = {
        "totalScore": report.total_score,
        "dimensionScores": json.loads(report.dimension_scores) if report.dimension_scores else [],
        "summary": report.summary,
        "perQuestionReviews": json.loads(report.per_question_reviews) if report.per_question_reviews else [],
        "resumeReview": json.loads(report.resume_review) if report.resume_review else None,
        "jobFit": report.job_fit,
        "matchScore": report.match_score,
        "matchBreakdown": json.loads(report.match_breakdown) if report.match_breakdown else [],
    }

    from server.services.pdf_service import generate_report_pdf

    pdf_bytes = generate_report_pdf(report_data)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=report_{interview_id}.pdf"
        },
    )


@router.post("/{interview_id}/share")
async def create_share_link(interview_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    """生成或刷新分享链接（7 天有效期）"""
    report = session.exec(
        select(Report).where(Report.interview_id == interview_id)
    ).first()
    if not report:
        raise HTTPException(404, "Report not found")

    interview = session.get(Interview, report.interview_id)
    if not interview or interview.user_id != user.id:
        raise HTTPException(404, "Report not found")

    report.share_token = _generate_share_token()
    report.share_expires_at = datetime.utcnow() + timedelta(days=SHARE_DEFAULT_DAYS)
    session.add(report)
    session.commit()
    session.refresh(report)

    return {
        "token": report.share_token,
        "expiresAt": report.share_expires_at.isoformat() if report.share_expires_at else None,
    }


@router.delete("/{interview_id}/share")
async def revoke_share_link(interview_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    """吊销分享链接"""
    report = session.exec(
        select(Report).where(Report.interview_id == interview_id)
    ).first()
    if not report:
        raise HTTPException(404, "Report not found")
    interview = session.get(Interview, report.interview_id)
    if not interview or interview.user_id != user.id:
        raise HTTPException(404, "Report not found")
    report.share_token = None
    report.share_expires_at = None
    session.add(report)
    session.commit()
    return {"ok": True}


@router.get("/{interview_id}/share-status")
async def get_share_status(interview_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    """查询当前分享状态"""
    report = session.exec(
        select(Report).where(Report.interview_id == interview_id)
    ).first()
    if not report:
        raise HTTPException(404, "Report not found")
    interview = session.get(Interview, report.interview_id)
    if not org_service.can_view_interview(session, user, interview):
        raise HTTPException(404, "Report not found")
    return {
        "token": report.share_token,
        "expiresAt": report.share_expires_at.isoformat() if report.share_expires_at else None,
        "expired": (
            report.share_expires_at is not None
            and report.share_expires_at < datetime.utcnow()
        ),
    }


# 公开分享路由（独立前缀，无鉴权）
share_router = APIRouter(prefix="/api/share", tags=["share"])


@share_router.get("/{token}")
async def get_shared_report(token: str, session: Session = Depends(get_session)):
    """通过分享 token 公开读取报告（无鉴权，校验有效期）"""
    report = session.exec(
        select(Report).where(Report.share_token == token)
    ).first()
    if not report:
        raise HTTPException(404, "Share link not found")
    if report.share_expires_at and report.share_expires_at < datetime.utcnow():
        raise HTTPException(410, "Share link expired")
    return _format_report(report)
