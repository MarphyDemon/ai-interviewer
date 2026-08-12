import json
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlmodel import Session, select
from server.database import get_session
from server.models import KnowledgeDoc
from server.services.knowledge_service import process_knowledge_doc, delete_knowledge
from server.services.common import get_or_create_user
import asyncio

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/upload")
async def upload_knowledge(
    files: list[UploadFile] = File(...),
    session: Session = Depends(get_session),
):
    user_uuid = "default"
    user_id = get_or_create_user(session, user_uuid)
    ids = []

    for file in files:
        if not file.filename.endswith(".md"):
            raise HTTPException(400, f"{file.filename} is not a Markdown file")

        content = await file.read()
        text = content.decode("utf-8")

        doc = KnowledgeDoc(
            user_id=user_id,
            filename=file.filename,
            content=text,
            status="processing",
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)
        ids.append(doc.id)

        asyncio.create_task(process_knowledge_doc_async(doc.id))

    return {"ids": ids}


async def process_knowledge_doc_async(doc_id: int):
    from server.database import engine
    with Session(engine) as session:
        await process_knowledge_doc(session, doc_id)


@router.get("")
async def list_knowledge(session: Session = Depends(get_session)):
    docs = session.exec(select(KnowledgeDoc)).all()
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "title": d.title,
            "position": d.position,
            "difficulty": d.difficulty,
            "tags": json.loads(d.tags) if d.tags else [],
            "status": d.status,
            "createdAt": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@router.get("/{doc_id}/status")
async def get_status(doc_id: int, session: Session = Depends(get_session)):
    doc = session.get(KnowledgeDoc, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return {"status": doc.status}


@router.delete("/{doc_id}")
async def delete_doc(doc_id: int, session: Session = Depends(get_session)):
    delete_knowledge(session, doc_id)
    return {"ok": True}
