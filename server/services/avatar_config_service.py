#! encoding=utf-8
"""具身交互智能体配置解析：默认配置一律来自数据库。

历史背景：v3.5 之前"默认"写死在 .env（AVATAR_APP_ID / AVATAR_APP_SECRET /
AVATAR_GATEWAY_SERVER / AVATAR_DEFAULT_IMAGE），改一次必须重启后端容器。
现在这些变量已退出运行时解析，仅在 database._seed_avatar_config_from_env()
中作为一次性搬迁的输入。

默认选取顺序（取第一条命中）：
1. is_default=True —— 管理员在管理后台显式指定（互斥）
2. is_active=True  —— 自动选择：启用中最新创建的一条
3. 任意记录        —— 兜底：全表最新创建的一条
4. 都没有          —— 返回 None，前端降级本地 Lottie 形象
"""
from typing import Optional

from sqlmodel import Session, select

from server.config import settings
from server.models import AvatarProviderConfig, User
from server.services.crypto_service import decrypt


def resolve_default_avatar_config(session: Session) -> Optional[AvatarProviderConfig]:
    """解析全站默认的具身交互智能体配置（无可用配置时返回 None）。"""
    cfg = session.exec(
        select(AvatarProviderConfig)
        .where(AvatarProviderConfig.is_default == True)  # noqa: E712
        .order_by(AvatarProviderConfig.created_at.desc())
    ).first()
    if cfg:
        return cfg

    cfg = session.exec(
        select(AvatarProviderConfig)
        .where(AvatarProviderConfig.is_active == True)  # noqa: E712
        .order_by(AvatarProviderConfig.created_at.desc())
    ).first()
    if cfg:
        return cfg

    return session.exec(
        select(AvatarProviderConfig).order_by(AvatarProviderConfig.created_at.desc())
    ).first()


def resolve_avatar_config_for_user(
    session: Session,
    user: Optional[User],
) -> Optional[AvatarProviderConfig]:
    """用户实际生效的配置：用户偏好（记录仍需存在）优先，否则用全站默认。"""
    if user is not None and user.preferred_avatar_config_id:
        cfg = session.get(AvatarProviderConfig, user.preferred_avatar_config_id)
        if cfg:
            return cfg
    return resolve_default_avatar_config(session)


def _asr_config_payload() -> dict:
    """SDK asr_config：凭证由后端下发，避免写死在打包产物里。

    未配置（缺 access_token / app_id）时返回 {}，让 SDK 使用自身默认 ASR 配置。
    """
    if not settings.asr_access_token or not settings.asr_app_id:
        return {}
    return {
        "provider": settings.asr_provider,
        "base_url": settings.asr_base_url,
        "headers": {
            "resource_id": settings.asr_resource_id,
            "access_token": settings.asr_access_token,
            "app_id": settings.asr_app_id,
        },
        "request": {
            "enable_ddc": False,
            "enable_itn": True,
            "model_name": "bigmodel",
            "enable_punc": True,
            "result_type": "full",
            "model_version": "400",
            "end_window_size": 200,
            "show_utterances": True,
            "force_to_speech_time": 1000,
        },
    }


def avatar_config_payload(cfg: Optional[AvatarProviderConfig]) -> dict:
    """前端 SDK 初始化载荷。无可用配置时返回 configured=False，前端据此降级 Lottie。"""
    if cfg is None:
        return {
            "configured": False,
            "appId": "",
            "appSecret": "",
            "gatewayServer": "",
            "avatarImage": "",
            "asrConfig": {},
        }
    return {
        "configured": True,
        "appId": cfg.app_id,
        "appSecret": decrypt(cfg.app_secret),
        "gatewayServer": cfg.gateway_server,
        "avatarImage": cfg.avatar_image,
        "asrConfig": _asr_config_payload(),
    }
