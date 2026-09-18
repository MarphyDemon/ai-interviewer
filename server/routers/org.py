"""企业侧控制台接口：组织、成员、候选人邀请与候选人排名。

权限：owner / hr 可管理（发邀请、加成员）；viewer 只读。个人用户首次访问
/api/org/me 时会自动开通一个组织并成为 owner（自助开通，不阻塞演示）。
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from server.database import get_session
from server.models import CandidateInvite, User
from server.services import org_service
from server.services.auth_service import get_current_user

router = APIRouter(prefix="/api/org", tags=["org"])


class InviteCreateRequest(BaseModel):
    position: str
    jdId: Optional[int] = None
    # 沿用前端词汇：junior|mid|senior、strict|friendly|pressure
    difficulty: str = "mid"
    duration: int = 30
    style: str = "friendly"
    note: str = ""
    # 本次面试的考察重点（HR 自定义，注入候选人面试的 prompt）
    focus: str = ""
    expiresInDays: int = 30


class MemberAddRequest(BaseModel):
    username: str
    role: str = "hr"


def _require_manager(session: Session, user: User, org_id: int) -> None:
    if not org_service.can_manage_invite(session, user, org_id):
        raise HTTPException(403, "需要组织管理员权限")


@router.get("/me")
async def my_org(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """当前用户所属组织（不存在则自动创建），并附带成员列表。"""
    org = org_service.get_or_create_org(session, user)
    role = org_service.member_role(session, org.id, user.id)
    invites = org_service.list_invites(session, org.id)
    return {
        "id": org.id,
        "name": org.name,
        "role": role,
        "canManage": role in org_service.ORG_MANAGER_ROLES,
        "members": org_service.list_members(session, org.id),
        "inviteCount": len(invites),
        "candidateCount": len(org_service.candidate_ranking(session, org.id, limit=1000)),
    }


@router.get("/invites")
async def list_invites(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    org = org_service.get_or_create_org(session, user)
    return org_service.list_invites(session, org.id)


@router.post("/invites")
async def create_invite(
    req: InviteCreateRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """创建候选人邀请，返回可直接发给候选人的 token。"""
    position = (req.position or "").strip()
    if not position:
        raise HTTPException(400, "请填写岗位方向")

    org = org_service.get_or_create_org(session, user)
    _require_manager(session, user, org.id)

    invite = org_service.create_invite(
        session,
        org,
        user,
        position=position,
        jd_id=req.jdId,
        difficulty=req.difficulty,
        duration=req.duration,
        style=req.style,
        note=req.note,
        focus=req.focus,
        expires_in_days=max(1, min(req.expiresInDays, 365)),
    )
    return {
        "id": invite.id,
        "token": invite.token,
        "path": f"/invite/{invite.token}",
        "position": invite.position,
        "expiresAt": invite.expires_at.isoformat() if invite.expires_at else None,
    }


@router.delete("/invites/{invite_id}")
async def revoke_invite(
    invite_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """吊销邀请：已生成的链接立即失效，已提交的面试与报告保留。"""
    invite = session.get(CandidateInvite, invite_id)
    if not invite:
        raise HTTPException(404, "邀请不存在")
    _require_manager(session, user, invite.org_id)

    invite.revoked = True
    session.add(invite)
    session.commit()
    return {"ok": True}


@router.get("/candidates")
async def candidate_list(
    inviteId: Optional[int] = Query(None, description="限定某次邀请"),
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """候选人成绩排名（按报告总分倒序，未出报告排最后）。"""
    org = org_service.get_or_create_org(session, user)
    if org_service.member_role(session, org.id, user.id) not in org_service.ORG_VIEWER_ROLES:
        raise HTTPException(403, "无权查看候选人名单")
    return org_service.candidate_ranking(session, org.id, invite_id=inviteId, limit=limit)


@router.get("/members")
async def list_members(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    org = org_service.get_or_create_org(session, user)
    return org_service.list_members(session, org.id)


@router.post("/members")
async def add_member(
    req: MemberAddRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """把已有用户加入组织（按用户名）。多 HR 协作时使用。"""
    org = org_service.get_or_create_org(session, user)
    _require_manager(session, user, org.id)
    try:
        member = org_service.add_member(session, org, req.username.strip(), req.role)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    return {"ok": True, "userId": member.user_id, "role": member.role}
