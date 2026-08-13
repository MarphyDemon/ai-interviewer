import json
import os
from pathlib import Path
from typing import Optional


def get_or_create_user(session, anonymous_uuid: str) -> int:
    from server.models import User

    user = session.query(User).filter(User.anonymous_uuid == anonymous_uuid).first()
    if user:
        return user.id

    user = User(anonymous_uuid=anonymous_uuid)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user.id


def get_active_llm_config(session):
    from server.models import LLMConfig
    from server.services.crypto_service import decrypt

    cfg = session.query(LLMConfig).filter(LLMConfig.is_active == True).first()
    if cfg:
        # 返回解密后的 key，不影响数据库存储
        cfg.api_key = decrypt(cfg.api_key)
        return cfg

    from server.config import settings

    return type("FallbackConfig", (), {
        "id": 0,
        "base_url": settings.llm_base_url,
        "api_key": settings.llm_api_key,
        "model": settings.llm_model,
    })()


def mask_api_key(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]
