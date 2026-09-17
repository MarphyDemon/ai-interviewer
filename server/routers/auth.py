"""用户认证路由：注册 / 登录 / 当前用户信息。

注册策略：开放注册（Q2），首用户继承 'default' 遗留数据（Q9）。
注册身份：个人练习（默认）与企业招聘；企业注册时传 orgName，自动建组织并成为 owner。
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Session, select

from server.database import get_session
from server.models import (
    User, Resume, Interview, ChatConversation, KnowledgeDoc, JobDescription,
    Organization, OrgMember, UserQuota,
)
from server.services.auth_service import (
    hash_password, verify_password, create_user_token, get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    password: str
    # 企业招聘注册时填写公司/团队名称，注册后自动建组织并成为 owner
    orgName: str = ""

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 32:
            raise ValueError("用户名长度需 3-32 个字符")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 8 or len(v) > 128:
            raise ValueError("密码长度需 8-128 位")
        return v

    @field_validator("orgName")
    @classmethod
    def org_name_valid(cls, v: str) -> str:
        v = (v or "").strip()
        if len(v) > 64:
            raise ValueError("公司名称长度不能超过 64 个字符")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/register")
async def register(req: RegisterRequest, session: Session = Depends(get_session)):
    existing = session.exec(select(User).where(User.username == req.username)).first()
    if existing:
        raise HTTPException(409, "用户名已存在")

    user = User(
        anonymous_uuid=uuid.uuid4().hex,
        username=req.username,
        password_hash=hash_password(req.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # 首用户继承 'default' 匿名用户的遗留数据（一次性迁移）
    _maybe_inherit_default_data(session, user.id)

    # 企业招聘身份：自动建组织并把注册者设为 owner
    if req.orgName:
        org = Organization(name=req.orgName, owner_id=user.id)
        session.add(org)
        session.commit()
        session.refresh(org)
        session.add(OrgMember(org_id=org.id, user_id=user.id, role="owner"))
        session.commit()

    token = create_user_token(user.id)
    return {"token": token, "user": _format_user(user, session)}


@router.post("/login")
async def login(req: LoginRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == req.username)).first()
    if not user or not user.password_hash:
        raise HTTPException(401, "用户名或密码错误")
    if not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    token = create_user_token(user.id)
    return {"token": token, "user": _format_user(user, session)}


@router.get("/me")
async def me(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return _format_user(user, session)


def _format_user(user: User, session: Session | None = None) -> dict:
    import json as _json
    notif = {}
    if user.notification_settings:
        try:
            notif = _json.loads(user.notification_settings)
        except Exception:
            notif = {}

    # 企业侧身份：套餐 + 组织角色（个人用户两者均为 free / None）
    plan = "free"
    org_role = None
    if session is not None:
        quota = session.exec(select(UserQuota).where(UserQuota.user_id == user.id)).first()
        plan = quota.plan if quota else "free"
        member = session.exec(
            select(OrgMember).where(OrgMember.user_id == user.id)
        ).first()
        org_role = member.role if member else None

    return {
        "id": user.id,
        # 候选人（role="candidate"）不占用户名，这里统一回空串，避免前端出现 null
        "username": user.username or "",
        "role": user.role,
        "preferredAvatarConfigId": user.preferred_avatar_config_id,
        "preferredPosition": user.preferred_position,
        "language": user.language,
        "theme": user.theme,
        "notificationSettings": notif,
        "plan": plan,
        "orgRole": org_role,
    }


def _maybe_inherit_default_data(session: Session, new_user_id: int) -> None:
    """首用户继承 'default' 匿名用户的遗留数据（一次性迁移，幂等）。

    迁移范围：Resume / Interview / ChatConversation / JobDescription 全量迁移；
    KnowledgeDoc 仅迁移 private（is_public=False），public 保留共享。
    若新用户已有自有数据，跳过迁移（避免重复）。
    """
    default_user = session.exec(
        select(User).where(User.anonymous_uuid == "default")
    ).first()
    if not default_user or default_user.id == new_user_id:
        return

    # 新用户已有自有数据则跳过（幂等保护）
    if session.exec(select(Resume).where(Resume.user_id == new_user_id)).first():
        return

    for model in (Resume, Interview, ChatConversation, JobDescription):
        items = session.exec(select(model).where(model.user_id == default_user.id)).all()
        for item in items:
            item.user_id = new_user_id
            session.add(item)

    # KnowledgeDoc：private 迁移，public 保留共享
    private_docs = session.exec(
        select(KnowledgeDoc).where(
            KnowledgeDoc.user_id == default_user.id,
            KnowledgeDoc.is_public == False,  # noqa: E712
        )
    ).all()
    for doc in private_docs:
        doc.user_id = new_user_id
        session.add(doc)

    session.commit()
