from datetime import datetime
from typing import AsyncGenerator, Optional
from sqlmodel import Session, select
from server.models import ChatConversation, ChatMessage
from server.services.common import get_active_llm_config
from server.services.rag_service import search
from server.embedding.siliconflow import get_embedding


async def _retrieve_knowledge(query: str, top_k: int = 5) -> str:
    """检索知识库（不过滤岗位），返回拼接的上下文。失败时返回空串，退化为纯 LLM 回答。"""
    try:
        embedding = await get_embedding(query)
        results = search(embedding, top_k=top_k)
        if not results:
            return ""
        return "\n---\n".join([r["content"] for r in results])
    except Exception as e:
        print(f"[Chat RAG] retrieval failed: {e}")
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


async def stream_chat(
    session: Session,
    conversation_id: int,
    user_message: str,
) -> AsyncGenerator[str, None]:
    """流式聊天：持久化用户消息 → RAG 检索 → 流式生成 → 持久化助手回复。"""
    # 1. 持久化用户消息
    session.add(ChatMessage(conversation_id=conversation_id, role="user", content=user_message))

    # 2. 首条消息自动生成标题
    conv = session.get(ChatConversation, conversation_id)
    if conv and (not conv.title or conv.title == "新对话"):
        conv.title = user_message[:20] + ("…" if len(user_message) > 20 else "")

    # 3. 取历史消息（含刚加入的用户消息）
    history = session.exec(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at)
    ).all()
    session.commit()

    # 4. RAG 检索知识库
    knowledge = await _retrieve_knowledge(user_message)

    # 5. 构建消息列表
    messages = [{"role": "system", "content": _build_system_prompt(knowledge)}]
    for m in history:
        messages.append({"role": m.role, "content": m.content})

    # 6. 流式生成
    cfg = get_active_llm_config(session)
    from openai import AsyncOpenAI

    client = AsyncOpenAI(base_url=cfg.base_url, api_key=cfg.api_key)
    full_response = ""
    stream = await client.chat.completions.create(
        model=cfg.model, messages=messages, stream=True
    )
    try:
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full_response += delta
                yield delta
    finally:
        # 无论正常结束还是客户端打断（GeneratorExit），都持久化已生成内容
        if full_response:
            session.add(ChatMessage(conversation_id=conversation_id, role="assistant", content=full_response))
            if conv:
                conv.updated_at = datetime.utcnow()
            session.commit()
