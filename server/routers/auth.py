"""用户认证路由：注册 / 登录 / 当前用户信息。

注册策略：开放注册（Q2），首用户继承 'default' 遗留数据（Q9）。
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Session, select

from server.database import get_session
from server.models import (
    User, Resume, Interview, ChatConversation, KnowledgeDoc, JobDescription,
)
from server.services.auth_service import (
    hash_password, verify_password, create_user_token, get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    password: str

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

    token = create_user_token(user.id)
    return {"token": token, "user": _format_user(user)}


@router.post("/login")
async def login(req: LoginRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == req.username)).first()
    if not user or not user.password_hash:
        raise HTTPException(401, "用户名或密码错误")
    if not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    token = create_user_token(user.id)
    return {"token": token, "user": _format_user(user)}


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return _format_user(user)


def _format_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "preferredAvatarId": user.preferred_avatar_id,
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
