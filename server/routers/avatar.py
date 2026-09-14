import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from server.config import settings
from server.database import get_session
from server.models import AvatarProviderConfig, AvatarSessionToken, ChatConversation, LLMConfig, User
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
from server.services.interview_brain_service import (
    resolve_interview_session,
    generate_interview_stream,
    generate_interview_non_stream,
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
    conversation_id: Optional[int] = Query(None, description="绑定的会话 ID"),
):
    """返回 SDK brain_config 格式的配置。

    两种模式：
    1. 代理模式（avatar_proxy_base_url 已配置）：返回代理 URL + session token，
       SDK 请求走 RAG+LLM 流水线。
       如果传入 conversation_id，token 绑定到已有会话；否则创建新会话。
    2. 直连模式（未配置 avatar_proxy_base_url）：返回真实 LLM 供应商配置，
       SDK 直接请求 LLM 供应商（本地开发友好）。
    """
    cfg = get_active_llm_config(session)

    if settings.avatar_proxy_base_url:
        # 代理模式：创建 session token
        # 如果前端指定了 conversation_id，则绑定到该会话，避免创建重复会话
        try:
            token_str, conv_id = create_session_token(session, user.id, conversation_id)
        except ValueError as e:
            raise HTTPException(404, str(e))

        conv = session.get(ChatConversation, conv_id)
        conv_title = conv.title if conv else "数字人对话"
        conv_created = conv.created_at.isoformat() if conv and conv.created_at else None

        proxy_base = settings.avatar_proxy_base_url.rstrip("/") + "/api/avatar/brain-proxy/v1"
        return {
            "provider": "openai",
            "model": cfg.model,
            "api_key": token_str,
            "base_url": proxy_base,
            "extra_body": {
                "temperature": 0.7,
            },
            "conversation": {
                "id": conv_id,
                "title": conv_title,
                "created_at": conv_created,
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
@router.post("/brain-proxy/v1/chat/completions")
async def brain_proxy_chat_completions(
    request: Request,
    session: Session = Depends(get_session),
    authorization: Optional[str] = Header(None),
):
    """SDK LLM 请求代理：校验 token → RAG 检索 → LLM 调用 → 返回标准 OpenAI SSE。

    按 token 归属分流：
    1. 面试 token（InterviewAvatarSession）→ 面试官大脑（interview_brain_service）
    2. 聊天 token（AvatarSessionToken）→ 聊天链路（avatar_brain_service）
    """
    # 1. 校验 token
    if not authorization or not authorization.startswith("Bearer "):
        print(f"[Brain Proxy] WARN: Missing/invalid Authorization header. headers={dict(request.headers)}")
        raise HTTPException(401, "Missing authorization")
    token_str = authorization.split(" ", 1)[1]

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

    sse_headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }

    # 4a. 面试链路
    interview_resolved = resolve_interview_session(session, token_str)
    if interview_resolved is not None:
        user, interview = interview_resolved
        print(f"[Brain Proxy] Auth OK (interview): user={user.id}, interview={interview.id}")
        if is_stream:
            return StreamingResponse(
                generate_interview_stream(user_message, interview.id),
                media_type="text/event-stream",
                headers=sse_headers,
            )
        return await generate_interview_non_stream(user_message, interview.id)

    # 4b. 聊天链路
    resolved = resolve_session(session, token_str)
    if resolved is None:
        print(f"[Brain Proxy] WARN: Session token not found or expired. token={token_str[:16]}...")
        raise HTTPException(401, "Invalid or expired session token")
    user, conv = resolved
    print(f"[Brain Proxy] Auth OK (chat): user={user.id}, conv={conv.id}")

    if is_stream:
        return StreamingResponse(
            generate_stream(session, conv.id, user_message),
            media_type="text/event-stream",
            headers=sse_headers,
        )
    else:
        result = await generate_non_stream(session, conv.id, user_message)
        return result


class BrainVerifyRequest(BaseModel):
    message: str = "你好，请做个自我介绍"


@router.post("/brain-verify")
async def brain_verify(
    payload: BrainVerifyRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """管理员验证端点：测试 RAG+LLM 代理链路是否正常。

    返回详细的调试信息：brain_config 内容、RAG 检索结果摘要、LLM 响应预览。
    """
    from server.services.avatar_brain_service import (
        create_session_token,
        _retrieve_knowledge,
        _build_system_prompt,
    )

    cfg = get_active_llm_config(session)
    token_str, conv_id = create_session_token(session, user.id)

    knowledge = await _retrieve_knowledge(payload.message)
    system_prompt = _build_system_prompt(knowledge)

    # 简单 LLM 调用测试（非流式，取前 200 字符预览）
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(base_url=cfg.base_url, api_key=cfg.api_key)
        llm_response = await client.chat.completions.create(
            model=cfg.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": payload.message},
            ],
            stream=False,
            max_tokens=500,
        )
        reply_preview = (llm_response.choices[0].message.content or "")[:200]
        llm_ok = True
        llm_error = None
    except Exception as e:
        reply_preview = ""
        llm_ok = False
        llm_error = str(e)

    proxy_base = settings.avatar_proxy_base_url or "(未配置，本地开发模式)"

    return {
        "brain_config": {
            "provider": "openai" if settings.avatar_proxy_base_url else "direct",
            "base_url": proxy_base,
            "model": cfg.model,
            "api_key_preview": cfg.api_key[:8] + "..." if len(cfg.api_key) > 8 else "***",
        },
        "token": {
            "token_preview": token_str[:16] + "..." if len(token_str) > 16 else token_str,
            "conversation_id": conv_id,
            "ttl_hours": 24,
        },
        "rag": {
            "knowledge_found": bool(knowledge),
            "knowledge_preview": knowledge[:300] if knowledge else "(无检索结果)",
        },
        "llm": {
            "ok": llm_ok,
            "model": cfg.model,
            "reply_preview": reply_preview,
            "error": llm_error,
        },
    }