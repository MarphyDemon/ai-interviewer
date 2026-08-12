import json
import asyncio
from typing import Optional
from sqlmodel import Session
from server.models import KnowledgeDoc
from server.parsers.markdown_parser import parse_markdown, chunk_markdown
from server.embedding.siliconflow import get_embedding
from server.services.rag_service import add_chunks, delete_doc_chunks


async def process_knowledge_doc(session: Session, doc_id: int):
    doc = session.get(KnowledgeDoc, doc_id)
    if not doc:
        return

    try:
        metadata, body = parse_markdown(doc.content)
        doc.title = metadata.get("title", doc.filename.replace(".md", ""))
        doc.position = metadata.get("position", "")
        doc.difficulty = metadata.get("difficulty", "")
        doc.tags = json.dumps(metadata.get("tags", []), ensure_ascii=False)

        chunks_raw = chunk_markdown(body)
        if not chunks_raw:
            doc.status = "failed"
            session.add(doc)
            session.commit()
            return

        chunks = [
            {
                "content": c["content"],
                "title": c["title"],
                "position": doc.position,
                "difficulty": doc.difficulty,
                "tags": doc.tags,
            }
            for c in chunks_raw
        ]

        embeddings = []
        for chunk in chunks:
            emb = await get_embedding(chunk["content"])
            embeddings.append(emb)

        add_chunks(doc_id=doc.id, chunks=chunks, embeddings=embeddings)
        doc.status = "ready"
    except Exception as e:
        print(f"[Knowledge] processing failed for doc {doc_id}: {e}")
        doc.status = "failed"

    session.add(doc)
    session.commit()


def delete_knowledge(session: Session, doc_id: int):
    doc = session.get(KnowledgeDoc, doc_id)
    if not doc:
        return
    delete_doc_chunks(doc_id)
    session.delete(doc)
    session.commit()
