"""数字人 Brain Proxy 服务：将 SDK 的 LLM 请求代理为 RAG+LLM 流水线。

核心流程：
1. 校验 session token → 获取用户身份与专属对话
2. 从 ChatCompletion 请求体提取最新 user 消息
3. 执行 RAG 检索（向量搜索 + 知识库）
4. 构建增强的 system prompt + 历史消息
5. 调用真实 LLM（流式/非流式）
6. 封装为标准 OpenAI SSE 格式返回给 SDK
"""
import json
import secrets
import time
from datetime import datetime, timedelta
from typing import AsyncGenerator, Optional

from sqlmodel import Session, select

from server.config import settings
from server.models import (
    AvatarSessionToken,
    ChatConversation,
    ChatMessage,
    User,
)
from server.services.common import get_active_llm_config


# ---------- Token 管理 ----------

TOKEN_TTL_HOURS = 24


def create_session_token(session: Session, user_id: int) -> tuple[str, int]:
    """为用户创建 avatar 会话 token + 专属对话。返回 (token, conversation_id)。

    每次调用都会创建新的 token 和对话；旧 token 可保留至过期。
    """
    conv = ChatConversation(
        user_id=user_id,
        title="数字人对话",
    )
    session.add(conv)
    session.commit()
    session.refresh(conv)

    token_str = secrets.token_hex(32)
    expires_at = datetime.utcnow() + timedelta(hours=TOKEN_TTL_HOURS)

    token_obj = AvatarSessionToken(
        user_id=user_id,
        token=token_str,
        conversation_id=conv.id,
        expires_at=expires_at,
    )
    session.add(token_obj)
    session.commit()

    return token_str, conv.id


def resolve_session(
    session: Session, token_str: str
) -> Optional[tuple[User, ChatConversation]]:
    """通过 session token 查找用户和对话。token 无效/过期返回 None。"""
    from server.services.crypto_service import decrypt

    token_obj = session.exec(
        select(AvatarSessionToken).where(AvatarSessionToken.token == token_str)
    ).first()
    if not token_obj:
        return None

    if datetime.utcnow() > token_obj.expires_at:
        return None

    user = session.get(User, token_obj.user_id)
    conv = session.get(ChatConversation, token_obj.conversation_id)
    if not user or not conv:
        return None

    return user, conv


# ---------- RAG + LLM 推理 ----------

async def _retrieve_knowledge(query: str, top_k: int = 5) -> str:
    from server.services.rag_service import search
    from server.embedding.siliconflow import get_embedding

    try:
        embedding = await get_embedding(query)
        results = search(embedding, top_k=top_k)
        if not results:
            return ""
        return "\n---\n".join([r["content"] for r in results])
    except Exception as e:
        print(f"[Avatar Brain] RAG retrieval failed: {e}")
        return ""


def _build_system_prompt(knowledge: str = "") -> str:
    base = (
        "你是一名耐心的技术学习导师（数字人），帮助用户学习面试相关知识。"
        "用户会就单个知识点提问，你基于下方知识库内容回答；"
        "如果知识库内容与问题无关，则忽略它，用你自己的知识作答。"
        "回答要清晰、准确、有条理，必要时给出代码示例。用中文回答。"
    )
    if knowledge:
        base += f"\n\n知识库参考（可能相关，请自行判断相关性）：\n{knowledge}"
    return base


def _extract_last_user_message(messages: list) -> str:
    """从 ChatCompletion messages 中提取最后一条 role=user 的消息内容。"""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                text_parts = [p.get("text", "") for p in content if p.get("type") == "text"]
                return "".join(text_parts)
    return ""


def _build_messages(
    session: Session,
    conversation_id: int,
    user_message: str,
    knowledge: str,
) -> list[dict]:
    """构建发给 LLM 的消息列表（system prompt + 对话历史 + 当前用户消息）。"""
    history = session.exec(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at)
    ).all()

    messages = [{"role": "system", "content": _build_system_prompt(knowledge)}]
    for m in history:
        messages.append({"role": m.role, "content": m.content})

    return messages


# ---------- 流式生成 ----------

async def generate_stream(
    session: Session,
    conversation_id: int,
    user_message: str,
) -> AsyncGenerator[str, None]:
    """流式生成：RAG 检索 → 调用 LLM → 输出标准 OpenAI SSE chunk。

    使用独立 session 操作数据库，避免依赖注入的 session 在异步流期间被关闭。
    """
    from server.database import engine
    import uuid
    from datetime import datetime as dt

    # 持久化用户消息
    session.add(
        ChatMessage(conversation_id=conversation_id, role="user", content=user_message)
    )
    conv = session.get(ChatConversation, conversation_id)
    if conv and (not conv.title or conv.title == "新对话"):
        conv.title = user_message[:20] + ("…" if len(user_message) > 20 else "")
    session.commit()

    # RAG 检索
    knowledge = await _retrieve_knowledge(user_message)
    messages = _build_messages(session, conversation_id, user_message, knowledge)

    cfg = get_active_llm_config(session)
    client = AsyncOpenAI(base_url=cfg.base_url, api_key=cfg.api_key)

    full_response = ""
    chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
    created_ts = int(dt.utcnow().timestamp())

    try:
        async for chunk in client.chat.completions.create(
            model=cfg.model, messages=messages, stream=True
        ):
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full_response += delta
                sse_chunk = json.dumps(
                    {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "created": created_ts,
                        "model": cfg.model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": delta},
                                "finish_reason": None,
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
                yield f"data: {sse_chunk}\n\n"
    except Exception as e:
        print(f"[Avatar Brain] Stream error: {e}")
    finally:
        # 发送 [DONE] 确保 SDK 正常关闭流
        yield "data: [DONE]\n\n"

        # 持久化 assistant 回复
        if full_response:
            try:
                with Session(engine) as db:
                    db.add(
                        ChatMessage(
                            conversation_id=conversation_id,
                            role="assistant",
                            content=full_response,
                        )
                    )
                    conv_ref = db.get(ChatConversation, conversation_id)
                    if conv_ref:
                        conv_ref.updated_at = dt.utcnow()
                    db.commit()
            except Exception as e:
                print(f"[Avatar Brain] Failed to save assistant message: {e}")


async def generate_non_stream(
    session: Session,
    conversation_id: int,
    user_message: str,
) -> dict:
    """非流式生成：RAG 检索 → 调用 LLM → 返回完整 JSON 响应。"""
    session.add(
        ChatMessage(conversation_id=conversation_id, role="user", content=user_message)
    )

    conv = session.get(ChatConversation, conversation_id)
    if conv and (not conv.title or conv.title == "新对话"):
        conv.title = user_message[:20] + ("…" if len(user_message) > 20 else "")

    knowledge = await _retrieve_knowledge(user_message)
    messages = _build_messages(session, conversation_id, user_message, knowledge)

    cfg = get_active_llm_config(session)
    from openai import AsyncOpenAI

    client = AsyncOpenAI(base_url=cfg.base_url, api_key=cfg.api_key)
    response = await client.chat.completions.create(
        model=cfg.model, messages=messages, stream=False
    )

    full_response = response.choices[0].message.content or ""

    if full_response:
        session.add(
            ChatMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=full_response,
            )
        )
        if conv:
            conv.updated_at = datetime.utcnow()
        session.commit()

    return response.model_dump()