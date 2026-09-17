import json
import traceback
from sqlmodel import Session, select
from server.models import KnowledgeDoc, KnowledgeVersion
from server.parsers.markdown_parser import parse_markdown, chunk_markdown
from server.embedding.siliconflow import get_embeddings_batch
from server.services.rag_service import add_chunks, delete_doc_chunks
from server.services.llm_service import llm_chat
from server.config import settings


async def _extract_metadata_from_content(content: str) -> dict:
    """用 LLM 从文档内容自动提取 position/difficulty/tags/title"""
    prompt = f"""分析以下面试题文档，提取元信息。严格输出 JSON，不要多余文字：
{{
  "title": "文档标题（简短）",
  "position": "岗位方向，如：前端/后端/算法/运维/测试",
  "difficulty": "难度：初级/中级/高级",
  "tags": ["标签1", "标签2"]
}}

文档内容（前2000字）：
{content[:2000]}"""

    try:
        result = await llm_chat(
            [{"role": "user", "content": prompt}],
            json_mode=True,
        )
        data = json.loads(result)
        return {
            "title": data.get("title", ""),
            "position": data.get("position", ""),
            "difficulty": data.get("difficulty", ""),
            "tags": data.get("tags", []),
        }
    except Exception as e:
        print(f"[Knowledge] LLM metadata extraction failed: {e}")
        return {}


async def process_knowledge_doc(session: Session, doc_id: int):
    doc = session.get(KnowledgeDoc, doc_id)
    if not doc:
        return

    try:
        metadata, body = parse_markdown(doc.content)
        doc.title = metadata.get("title", "")
        doc.position = metadata.get("position", "")
        doc.difficulty = metadata.get("difficulty", "")
        doc.tags = json.dumps(metadata.get("tags", []), ensure_ascii=False)

        # frontmatter 缺失 position 时，用 LLM 从内容自动提取
        if not doc.position:
            extracted = await _extract_metadata_from_content(body)
            if extracted:
                doc.title = doc.title or extracted.get("title", "")
                doc.position = extracted.get("position", "")
                doc.difficulty = doc.difficulty or extracted.get("difficulty", "")
                if not json.loads(doc.tags):
                    doc.tags = json.dumps(extracted.get("tags", []), ensure_ascii=False)

        if not doc.title:
            doc.title = doc.filename.replace(".md", "")

        chunks_raw = chunk_markdown(body)
        if not chunks_raw:
            doc.status = "failed"
            session.add(doc)
            session.commit()
            return

        chunks = [
            {
                "content": c["content"],
                "title": doc.title,
                "position": doc.position,
                "difficulty": doc.difficulty,
                "tags": doc.tags,
            }
            for c in chunks_raw
        ]

        # 批量获取 embedding，一次最多 32 条
        texts = [c["content"] for c in chunks]
        embeddings = await get_embeddings_batch(texts)

        add_chunks(doc_id=doc.id, chunks=chunks, embeddings=embeddings)
        doc.status = "ready"

        # 自动创建版本快照
        try:
            existing_versions = session.exec(
                select(KnowledgeVersion).where(KnowledgeVersion.doc_id == doc.id)
            ).all()
            next_version = max((v.version_number for v in existing_versions), default=0) + 1
            ver = KnowledgeVersion(
                doc_id=doc.id,
                version_number=next_version,
                content=doc.content,
                title=doc.title,
                position=doc.position,
                difficulty=doc.difficulty,
                tags=doc.tags,
                change_note=f"自动快照：处理完成 v{next_version}",
                created_by=doc.user_id,
            )
            session.add(ver)
        except Exception as ve:
            print(f"[Knowledge] version snapshot failed for doc {doc_id}: {ve}")
    except Exception as e:
        print(f"[Knowledge] processing failed for doc {doc_id}: {e}")
        traceback.print_exc()
        doc.status = "failed"

    session.add(doc)
    session.commit()


def delete_knowledge(session: Session, doc_id: int):
    doc = session.get(KnowledgeDoc, doc_id)
    if not doc:
        return
    if not settings.offline_mode:
        # 离线规则模式从未写入向量库，无需清理
        delete_doc_chunks(doc_id)
    session.delete(doc)
    session.commit()
