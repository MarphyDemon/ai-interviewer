import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select
from server.database import get_session, engine
from server.models import ChatConversation, ChatMessage
from server.services.common import get_or_create_user
from server.services.chat_service import stream_chat

router = APIRouter(prefix="/api/chat", tags=["chat"])


class CreateConversationIn(BaseModel):
    title: Optional[str] = None


class RenameIn(BaseModel):
    title: str


class MessageIn(BaseModel):
    message: str


@router.post("/conversations")
def create_conversation(payload: CreateConversationIn, session: Session = Depends(get_session)):
    user_id = get_or_create_user(session, "default")
    conv = ChatConversation(user_id=user_id, title=payload.title or "新对话")
    session.add(conv)
    session.commit()
    session.refresh(conv)
    return {
        "id": conv.id,
        "title": conv.title,
        "createdAt": conv.created_at.isoformat() if conv.created_at else None,
        "updatedAt": conv.updated_at.isoformat() if conv.updated_at else None,
    }


@router.get("/conversations")
def list_conversations(session: Session = Depends(get_session)):
    convs = session.exec(
        select(ChatConversation).order_by(ChatConversation.updated_at.desc())
    ).all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "createdAt": c.created_at.isoformat() if c.created_at else None,
            "updatedAt": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in convs
    ]


@router.get("/conversations/{conv_id}/messages")
def get_messages(conv_id: int, session: Session = Depends(get_session)):
    conv = session.get(ChatConversation, conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    msgs = session.exec(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conv_id)
        .order_by(ChatMessage.created_at)
    ).all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "createdAt": m.created_at.isoformat() if m.created_at else None,
        }
        for m in msgs
    ]


@router.patch("/conversations/{conv_id}")
def rename_conversation(conv_id: int, payload: RenameIn, session: Session = Depends(get_session)):
    conv = session.get(ChatConversation, conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    conv.title = payload.title
    session.add(conv)
    session.commit()
    return {"ok": True, "title": conv.title}


@router.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: int, session: Session = Depends(get_session)):
    conv = session.get(ChatConversation, conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    msgs = session.exec(
        select(ChatMessage).where(ChatMessage.conversation_id == conv_id)
    ).all()
    for m in msgs:
        session.delete(m)
    session.delete(conv)
    session.commit()
    return {"ok": True}


@router.post("/conversations/{conv_id}/messages/stream")
async def chat_stream(conv_id: int, payload: MessageIn):
    # 校验会话存在
    with Session(engine) as check_session:
        if not check_session.get(ChatConversation, conv_id):
            raise HTTPException(404, "Conversation not found")

    async def event_stream():
        # 流期间独立 session，随流结束自动关闭
        with Session(engine) as session:
            try:
                async for delta in stream_chat(session, conv_id, payload.message):
                    yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
