from typing import AsyncGenerator, Optional
from openai import AsyncOpenAI
from sqlmodel import Session
from fastapi import HTTPException
from server.services.common import get_active_llm_config
from server.services import offline_service


def get_llm_client(session: Session) -> tuple[AsyncOpenAI, str]:
    cfg = get_active_llm_config(session)
    api_key = cfg.api_key
    if not api_key or api_key.startswith("<"):
        raise HTTPException(
            500,
            "LLM API Key 未配置。请在 server/.env 中填入 LLM_API_KEY，或在管理页配置 LLM 供应商。"
            "若没有云端凭证，可改用本地大模型或离线规则模式（见 README「Docker 部署」）。",
        )
    return AsyncOpenAI(base_url=cfg.base_url, api_key=api_key), cfg.model


async def llm_chat(
    messages: list[dict],
    session: Optional[Session] = None,
    json_mode: bool = False,
) -> str:
    if offline_service.enabled():
        return offline_service.answer(messages, json_mode=json_mode)

    if session:
        client, model = get_llm_client(session)
    else:
        from server.config import settings

        if not settings.llm_api_key or settings.llm_api_key.startswith("<"):
            raise HTTPException(
                500,
                "LLM API Key 未配置。请在 server/.env 中填入 LLM_API_KEY，或在管理页配置 LLM 供应商。",
            )
        client = AsyncOpenAI(
            base_url=settings.llm_base_url, api_key=settings.llm_api_key
        )
        model = settings.llm_model

    kwargs: dict = {"model": model, "messages": messages}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    resp = await client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


async def llm_chat_stream(
    messages: list[dict],
    session: Optional[Session] = None,
) -> AsyncGenerator[str, None]:
    """流式 LLM 对话，逐 chunk 产出文本。"""
    if offline_service.enabled():
        async for delta in offline_service.stream(messages):
            yield delta
        return

    if session:
        client, model = get_llm_client(session)
    else:
        from server.config import settings

        if not settings.llm_api_key or settings.llm_api_key.startswith("<"):
            raise HTTPException(
                500,
                "LLM API Key 未配置。请在 server/.env 中填入 LLM_API_KEY，或在管理页配置 LLM 供应商。",
            )
        client = AsyncOpenAI(
            base_url=settings.llm_base_url, api_key=settings.llm_api_key
        )
        model = settings.llm_model

    stream = await client.chat.completions.create(
        model=model, messages=messages, stream=True
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        if delta:
            yield delta
