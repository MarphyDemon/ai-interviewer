import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from server.config import settings
from server.database import get_session
from server.models import AvatarProviderConfig, AvatarSessionToken, LLMConfig, User
from server.services.crypto_service import decrypt
from server.services.auth_service import get_current_user
from server.services.common import get_active_llm_config
from server.services.avatar_brain_service import (
    create_session_token,
    resolve_session,
    generate_stream,
    generate_non_stream,
    _extract_last_user_message,
)

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


@router.get("/brain-config")
async def get_brain_config(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """返回 SDK brain_config 格式的配置。

    两种模式：
    1. 代理模式（avatar_proxy_base_url 已配置）：返回代理 URL + session token，
       SDK 请求走 RAG+LLM 流水线。
    2. 直连模式（未配置 avatar_proxy_base_url）：返回真实 LLM 供应商配置，
       SDK 直接请求 LLM 供应商（本地开发友好）。
    """
    cfg = get_active_llm_config(session)

    if settings.avatar_proxy_base_url:
        # 代理模式：创建 session token + avatar 对话
        token_str, conv_id = create_session_token(session, user.id)
        return {
            "provider": "custom",
            "model": cfg.model,
            "api_key": token_str,
            "base_url": settings.avatar_proxy_base_url.rstrip("/") + "/api/avatar/brain-proxy",
            "extra_body": {
                "temperature": 0.7,
            },
        }
    else:
        # 直连模式：返回真实 LLM 配置
        provider = "deepseek"
        base_url = cfg.base_url
        if "volces" in base_url or "ark" in base_url:
            provider = "volces"
        elif "siliconflow" in base_url:
            provider = "siliconflow"
        elif "openrouter" in base_url:
            provider = "openrouter"
        elif "together" in base_url:
            provider = "together"

        return {
            "provider": provider,
            "model": cfg.model,
            "api_key": cfg.api_key,
            "base_url": cfg.base_url,
            "extra_body": {
                "temperature": 0.7,
            },
        }


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: list
    stream: Optional[bool] = True
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None


@router.post("/brain-proxy/chat/completions")
async def brain_proxy_chat_completions(
    request: Request,
    session: Session = Depends(get_session),
    authorization: Optional[str] = None,
):
    """SDK LLM 请求代理：校验 token → RAG 检索 → LLM 调用 → 返回标准 OpenAI SSE。"""
    # 1. 校验 token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing authorization")
    token_str = authorization.split(" ", 1)[1]

    resolved = resolve_session(session, token_str)
    if resolved is None:
        raise HTTPException(401, "Invalid or expired session token")
    user, conv = resolved

    # 2. 解析请求体
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")

    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(400, "Missing messages")

    is_stream = body.get("stream", True)

    # 3. 提取用户消息
    user_message = _extract_last_user_message(messages)
    if not user_message:
        raise HTTPException(400, "No user message found in messages")

    # 4. 流式或非流式
    if is_stream:
        async def event_stream():
            async for delta in generate_stream(session, conv.id, user_message):
                chunk = json.dumps(
                    {
                        "choices": [
                            {
                                "delta": {"content": delta},
                                "finish_reason": None,
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        result = await generate_non_stream(session, conv.id, user_message)
        return result