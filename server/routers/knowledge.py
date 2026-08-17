import json
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlmodel import Session, select, or_
from server.database import get_session
from server.models import KnowledgeDoc, User
from server.services.knowledge_service import process_knowledge_doc, delete_knowledge
from server.services.auth_service import get_current_user
import asyncio

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/upload")
async def upload_knowledge(
    files: list[UploadFile] = File(...),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    ids = []

    for file in files:
        if not file.filename.endswith(".md"):
            raise HTTPException(400, f"{file.filename} is not a Markdown file")

        content = await file.read()
        text = content.decode("utf-8")

        doc = KnowledgeDoc(
            user_id=user.id,
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
async def list_knowledge(session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    docs = session.exec(
        select(KnowledgeDoc).where(or_(KnowledgeDoc.user_id == user.id, KnowledgeDoc.is_public == True))
    ).all()
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


# 兜底默认岗位列表（DB 无数据时使用）
_DEFAULT_POSITIONS = ["前端", "后端", "算法", "产品", "测试", "测试开发", "运维"]


@router.get("/positions")
async def list_positions(session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    """返回 DB distinct position + 兜底默认列表，合并去重"""
    rows = session.exec(
        select(KnowledgeDoc.position).where(KnowledgeDoc.position != "", or_(KnowledgeDoc.user_id == user.id, KnowledgeDoc.is_public == True)).distinct()
    ).all()
    positions = [p for p in rows if p]
    # 合并兜底列表，去重保序
    seen = set(positions)
    for p in _DEFAULT_POSITIONS:
        if p not in seen:
            positions.append(p)
            seen.add(p)
    return {"positions": positions}


@router.get("/{doc_id}/status")
async def get_status(doc_id: int, session: Session = Depends(get_session)):
    doc = session.get(KnowledgeDoc, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return {"status": doc.status}


@router.post("/reindex")
async def reindex_all(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """重新索引所有已存在的知识库文档（迁移后使用）"""
    docs = session.exec(
        select(KnowledgeDoc).where(
            KnowledgeDoc.status == "ready",
            or_(KnowledgeDoc.user_id == user.id, KnowledgeDoc.is_public == True),
        )
    ).all()
    reindexed = 0
    for doc in docs:
        delete_doc_chunks(doc.id)
        asyncio.create_task(process_knowledge_doc_async(doc.id))
        reindexed += 1
    return {"reindexed": reindexed, "message": "正在重建向量索引，请稍后刷新查看"}


@router.delete("/{doc_id}")
async def delete_doc(doc_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    doc = session.get(KnowledgeDoc, doc_id)
    if not doc or doc.user_id != user.id:
        raise HTTPException(404, "Document not found")
    delete_knowledge(session, doc_id)
    return {"ok": True}
