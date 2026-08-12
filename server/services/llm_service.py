from typing import Optional
from openai import AsyncOpenAI
from sqlmodel import Session
from fastapi import HTTPException
from server.services.common import get_active_llm_config


def get_llm_client(session: Session) -> tuple[AsyncOpenAI, str]:
    cfg = get_active_llm_config(session)
    api_key = cfg.api_key
    if not api_key or api_key.startswith("<"):
        raise HTTPException(
            500,
            "LLM API Key 未配置。请在 server/.env 中填入 LLM_API_KEY，或在管理页配置 LLM 供应商。",
        )
    return AsyncOpenAI(base_url=cfg.base_url, api_key=api_key), cfg.model


async def llm_chat(
    messages: list[dict],
    session: Optional[Session] = None,
    json_mode: bool = False,
) -> str:
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
