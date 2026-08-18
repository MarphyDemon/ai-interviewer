import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from server.config import settings
from server.database import get_session
from server.models import AvatarProviderConfig, User
from server.services.crypto_service import decrypt
from server.services.auth_service import get_current_user

router = APIRouter(prefix="/api/avatar", tags=["avatar"])


@router.get("/config")
async def get_avatar_config(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """前端数字人 SDK 初始化配置。

    优先使用用户选择的数字人配置，无则降级到 .env 默认配置。
    """
    # 1. 尝试用户偏好的数字人配置
    if user.preferred_avatar_config_id:
        cfg = session.get(AvatarProviderConfig, user.preferred_avatar_config_id)
        if cfg:
            return {
                "appId": cfg.app_id,
                "appSecret": decrypt(cfg.app_secret),
                "gatewayServer": cfg.gateway_server,
                "avatarImage": cfg.avatar_image or settings.avatar_default_image,
                "asrConfig": {},
            }

    # 2. 降级到 .env 默认配置
    return {
        "appId": settings.avatar_app_id,
        "appSecret": settings.avatar_app_secret,
        "gatewayServer": settings.avatar_gateway_server,
        "avatarImage": settings.avatar_default_image,
        "asrConfig": {},
    }


@router.get("/homepage-avatars")
async def get_homepage_avatars(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """获取首页展示的所有数字人形象。

    包含：
    1. .env 默认形象（始终展示，无配置时的 fallback）
    2. 管理后台启用的（is_active=True）数字人配置
    """
    result = []

    # 1. .env 默认形象始终展示
    result.append({
        "id": None,
        "name": "默认数字人",
        "avatarImage": settings.avatar_default_image,
        "isDefault": True,
    })

    # 2. 管理后台启用的配置（is_active 表示"首页展示"）
    active_configs = session.exec(
        select(AvatarProviderConfig).where(AvatarProviderConfig.is_active == True)  # noqa: E712
    ).all()
    for cfg in active_configs:
        result.append({
            "id": cfg.id,
            "name": cfg.name,
            "avatarImage": cfg.avatar_image or settings.avatar_default_image,
            "isDefault": False,
        })

    # 标记用户当前选择
    preferred_id = user.preferred_avatar_config_id
    for item in result:
        item["isSelected"] = (
            (preferred_id is None and item["isDefault"]) or
            (preferred_id is not None and item["id"] == preferred_id)
        )

    return result


class PreferenceRequest(BaseModel):
    avatarConfigId: int | None = None


@router.put("/preference")
async def set_avatar_preference(
    req: PreferenceRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """设置当前用户的偏好数字人形象。

    avatarConfigId 为 None 时表示使用 .env 默认配置。
    """
    if req.avatarConfigId is not None:
        cfg = session.get(AvatarProviderConfig, req.avatarConfigId)
        if not cfg:
            raise HTTPException(404, "Avatar config not found")
    user.preferred_avatar_config_id = req.avatarConfigId
    session.add(user)
    session.commit()
    return {"ok": True, "preferredAvatarConfigId": user.preferred_avatar_config_id}
