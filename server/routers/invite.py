"""候选人邀请入口（公开接口，无需登录）。

HR 在组织控制台创建邀请后，把链接 /invite/{token} 发给候选人；
候选人填写姓名即可开始面试——后端为其创建一个 role="candidate" 的无密码 User，
并直接返回该 User 的登录 token，因此后续作答走的完全是个人练习那套接口。
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from server.database import get_session
from server.models import CandidateInvite, JobDescription, Organization
from server.services import org_service
from server.services.auth_service import create_user_token
from server.services.interview_service import start_interview_session

router = APIRouter(prefix="/api/invite", tags=["invite"])


class CandidateStartRequest(BaseModel):
    name: str
    email: str = ""
    lang: str = "en"


def _format_invite(session: Session, invite: CandidateInvite) -> dict:
    jd = session.get(JobDescription, invite.jd_id) if invite.jd_id else None
    org = session.get(Organization, invite.org_id)
    return {
        "position": invite.position,
        "jdTitle": jd.title if jd else "",
        "orgName": org.name if org else "",
        "difficulty": invite.difficulty,
        "duration": invite.duration,
        "style": invite.style,
        "note": invite.note,
        "active": org_service.invite_is_active(invite),
        "expiresAt": invite.expires_at.isoformat() if invite.expires_at else None,
    }


@router.get("/{token}")
async def get_invite(token: str, session: Session = Depends(get_session)):
    """候选人打开链接时读取的邀请信息（含失效状态，供前端提示）。"""
    invite = session.exec(
        select(CandidateInvite).where(CandidateInvite.token == token)
    ).first()
    if not invite:
        raise HTTPException(404, "邀请链接无效")
    return _format_invite(session, invite)


@router.post("/{token}/start")
async def start_by_invite(
    token: str,
    req: CandidateStartRequest,
    session: Session = Depends(get_session),
):
    """候选人填姓名后开始面试，返回可直接使用的登录 token。"""
    invite = session.exec(
        select(CandidateInvite).where(CandidateInvite.token == token)
    ).first()
    if not invite:
        raise HTTPException(404, "邀请链接无效")
    if not org_service.invite_is_active(invite):
        raise HTTPException(410, "邀请链接已失效，请联系面试官重新发送")

    name = (req.name or "").strip()
    if not name:
        raise HTTPException(400, "请填写姓名")

    candidate_user = org_service.register_candidate(session, invite, name, req.email)

    result = await start_interview_session(
        session,
        user_id=candidate_user.id,
        position=invite.position,
        difficulty=invite.difficulty,
        duration=invite.duration,
        style=invite.style,
        jd_id=invite.jd_id,
        lang=req.lang,
        org_id=invite.org_id,
        focus=invite.focus,
    )
    interview = result["interview"]

    return {
        "token": create_user_token(candidate_user.id),
        "candidateName": name,
        "interviewId": interview.id,
        "stage": result["stage"],
        "firstQuestion": result["firstQuestion"],
        # 前端面试页依赖 config 计算倒计时，故与个人练习的 /start 保持一致地回传；
        # difficulty / style 回传前端词汇，与 InterviewSetupView 的取值口径一致
        "config": {
            "position": interview.position,
            "difficulty": invite.difficulty,
            "duration": interview.duration,
            "style": invite.style,
        },
    }
