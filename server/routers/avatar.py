import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from server.config import settings
from server.database import get_session
from server.models import AvatarProviderConfig, Avatar, User
from server.services.crypto_service import decrypt
from server.services.auth_service import get_current_user

router = APIRouter(prefix="/api/avatar", tags=["avatar"])


@router.get("/config")
async def get_avatar_config(session: Session = Depends(get_session)):
    """前端数字人 SDK 初始化配置。

    优先从 DB 激活的 AvatarProviderConfig 读取，无则降级到 .env（兼容旧部署）。
    """
    cfg = session.exec(
        select(AvatarProviderConfig).where(AvatarProviderConfig.is_active == True)  # noqa: E712
    ).first()
    if cfg:
        return {
            "appId": cfg.app_id,
            "appSecret": decrypt(cfg.app_secret),
            "gatewayServer": cfg.gateway_server,
            "asrConfig": {},
        }
    return {
        "appId": settings.avatar_app_id,
        "appSecret": settings.avatar_app_secret,
        "gatewayServer": settings.avatar_gateway_server,
        "asrConfig": {},
    }


@router.get("/list")
async def list_avatars(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """数字人形象目录（用户级选择，资源后补）。"""
    avatars = session.exec(
        select(Avatar).where(Avatar.is_active == True)  # noqa: E712
    ).all()
    return [
        {
            "id": a.id,
            "name": a.name,
            "coverUrl": a.cover_url,
            "extra": json.loads(a.extra) if a.extra else {},
        }
        for a in avatars
    ]


class PreferenceRequest(BaseModel):
    avatarId: int


@router.put("/preference")
async def set_avatar_preference(
    req: PreferenceRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """设置当前用户的偏好数字人形象。"""
    avatar = session.get(Avatar, req.avatarId)
    if not avatar:
        raise HTTPException(404, "Avatar not found")
    user.preferred_avatar_id = req.avatarId
    session.add(user)
    session.commit()
    return {"ok": True, "preferredAvatarId": user.preferred_avatar_id}
