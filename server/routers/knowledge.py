import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select, or_
from server.database import get_session
from server.models import KnowledgeDoc, KnowledgeVersion, KnowledgeEditLock, KnowledgeCollaborator, User
from server.services import org_service
from server.services.knowledge_service import process_knowledge_doc, delete_knowledge
from server.services.rag_service import delete_doc_chunks
from server.services.auth_service import get_current_user, require_admin
import asyncio

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class CreateVersionRequest(BaseModel):
    changeNote: str = ""


class RollbackRequest(BaseModel):
    pass


class CollaboratorRequest(BaseModel):
    userId: int
    permission: str = "read"  # read / edit / admin


class LockResponse(BaseModel):
    locked: bool = True
    lockId: int | None = None


def _get_doc_or_404(session: Session, doc_id: int, user: User) -> KnowledgeDoc:
    doc = session.get(KnowledgeDoc, doc_id)
    if not doc:
        raise HTTPException(404, "文档不存在")
    if doc.user_id != user.id and not doc.is_public:
        # 企业知识库：同组织成员（owner/hr/viewer）均可访问
        if org_service.can_view_org_resource(session, user, doc.user_id, doc.org_id):
            return doc
        # Check collaborator permissions
        collab = session.exec(
            select(KnowledgeCollaborator).where(
                KnowledgeCollaborator.doc_id == doc_id,
                KnowledgeCollaborator.user_id == user.id,
            )
        ).first()
        if not collab:
            raise HTTPException(403, "无权限访问此文档")
    return doc


def _visible_doc_conditions(session: Session, user: User) -> list:
    """可见知识文档：本人 ∪ 全局公开 ∪ 所在组织知识库。"""
    conditions = [
        KnowledgeDoc.user_id == user.id,
        KnowledgeDoc.is_public == True,  # noqa: E712
    ]
    org_id = org_service.user_org_id(session, user.id)
    if org_id:
        conditions.append(KnowledgeDoc.org_id == org_id)
    return conditions


@router.post("/upload")
async def upload_knowledge(
    files: list[UploadFile] = File(...),
    scope: str = Form("personal"),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """上传知识文档。scope=org 时归属到企业组织，供全组织面试 RAG 使用。"""
    org_id = None
    if scope == "org":
        org_id = org_service.user_org_id(session, user.id)
        if not org_id:
            raise HTTPException(403, "当前账号未加入任何企业组织，无法上传企业知识库")
        if not org_service.can_manage_invite(session, user, org_id):
            raise HTTPException(403, "需要组织管理员权限（owner / hr）")

    ids = []

    for file in files:
        if not file.filename.endswith(".md"):
            raise HTTPException(400, f"{file.filename} is not a Markdown file")

        content = await file.read()
        text = content.decode("utf-8")

        doc = KnowledgeDoc(
            user_id=user.id,
            org_id=org_id,
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
        select(KnowledgeDoc).where(or_(*_visible_doc_conditions(session, user)))
    ).all()
    my_org_id = org_service.user_org_id(session, user.id)
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "title": d.title,
            "position": d.position,
            "difficulty": d.difficulty,
            "tags": json.loads(d.tags) if d.tags else [],
            "status": d.status,
            # 归属：org 表示企业知识库（全组织共享），personal 表示本人上传
            "scope": "org" if (d.org_id and d.org_id == my_org_id) else "personal",
            "orgId": d.org_id,
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
        select(KnowledgeDoc.position).where(
            KnowledgeDoc.position != "", or_(*_visible_doc_conditions(session, user))
        ).distinct()
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
            or_(*_visible_doc_conditions(session, user)),
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
    """删除文档：本人可删自己的文档；企业知识库由组织管理角色（owner/hr）可删。"""
    doc = session.get(KnowledgeDoc, doc_id)
    if not doc or not org_service.can_manage_org_resource(session, user, doc.user_id, doc.org_id):
        raise HTTPException(404, "Document not found")
    delete_knowledge(session, doc_id)
    return {"ok": True}


# ---------- 版本管理（P1 新增） ----------

@router.get("/{doc_id}/versions")
async def list_versions(
    doc_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    _get_doc_or_404(session, doc_id, user)  # 校验文档存在与访问权限
    versions = session.exec(
        select(KnowledgeVersion)
        .where(KnowledgeVersion.doc_id == doc_id)
        .order_by(KnowledgeVersion.version_number.desc())
    ).all()
    return [
        {
            "id": v.id,
            "versionNumber": v.version_number,
            "title": v.title,
            "changeNote": v.change_note,
            "createdBy": v.created_by,
            "createdAt": v.created_at.isoformat() if v.created_at else None,
        }
        for v in versions
    ]


@router.get("/{doc_id}/versions/{version_id}")
async def get_version(
    doc_id: int,
    version_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    _get_doc_or_404(session, doc_id, user)  # 校验文档存在与访问权限
    version = session.get(KnowledgeVersion, version_id)
    if not version or version.doc_id != doc_id:
        raise HTTPException(404, "版本不存在")
    return {
        "id": version.id,
        "versionNumber": version.version_number,
        "content": version.content,
        "title": version.title,
        "position": version.position,
        "difficulty": version.difficulty,
        "tags": json.loads(version.tags) if version.tags else [],
        "changeNote": version.change_note,
        "createdBy": version.created_by,
        "createdAt": version.created_at.isoformat() if version.created_at else None,
    }


@router.post("/{doc_id}/versions")
async def create_version(
    doc_id: int,
    req: CreateVersionRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    doc = _get_doc_or_404(session, doc_id, user)
    if doc.user_id != user.id:
        raise HTTPException(403, "只有文档所有者可创建手动版本")
    existing = session.exec(
        select(KnowledgeVersion).where(KnowledgeVersion.doc_id == doc_id)
    ).all()
    next_version = max((v.version_number for v in existing), default=0) + 1
    ver = KnowledgeVersion(
        doc_id=doc_id,
        version_number=next_version,
        content=doc.content,
        title=doc.title,
        position=doc.position,
        difficulty=doc.difficulty,
        tags=doc.tags,
        change_note=req.changeNote or f"手动保存 v{next_version}",
        created_by=user.id,
    )
    session.add(ver)
    session.commit()
    session.refresh(ver)
    return {"id": ver.id, "versionNumber": ver.version_number}


@router.post("/{doc_id}/versions/{version_id}/rollback")
async def rollback_version(
    doc_id: int,
    version_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    doc = _get_doc_or_404(session, doc_id, user)
    if doc.user_id != user.id:
        raise HTTPException(403, "只有文档所有者可回滚")
    version = session.get(KnowledgeVersion, version_id)
    if not version or version.doc_id != doc_id:
        raise HTTPException(404, "版本不存在")

    # 创建当前版本快照（回滚前先保存当前状态）
    existing = session.exec(
        select(KnowledgeVersion).where(KnowledgeVersion.doc_id == doc_id)
    ).all()
    snapshot_version = max((v.version_number for v in existing), default=0) + 1
    snapshot = KnowledgeVersion(
        doc_id=doc_id,
        version_number=snapshot_version,
        content=doc.content,
        title=doc.title,
        position=doc.position,
        difficulty=doc.difficulty,
        tags=doc.tags,
        change_note=f"回滚前自动快照（回滚到 v{version.version_number}）",
        created_by=user.id,
    )
    session.add(snapshot)

    # 回滚文档内容
    doc.content = version.content
    doc.title = version.title
    doc.position = version.position
    doc.difficulty = version.difficulty
    doc.tags = version.tags
    doc.status = "processing"
    session.add(doc)
    session.commit()

    # 重新索引
    asyncio.create_task(process_knowledge_doc_async(doc_id))
    return {"ok": True, "newVersion": snapshot_version}


@router.delete("/{doc_id}/versions/{version_id}")
async def delete_version(
    doc_id: int,
    version_id: int,
    session: Session = Depends(get_session),
    admin_user: User = Depends(require_admin),
):
    version = session.get(KnowledgeVersion, version_id)
    if not version or version.doc_id != doc_id:
        raise HTTPException(404, "版本不存在")
    session.delete(version)
    session.commit()
    return {"ok": True}


# ---------- 协作锁（P1-2 新增） ----------

@router.post("/{doc_id}/lock")
async def acquire_lock(
    doc_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    _get_doc_or_404(session, doc_id, user)  # 校验文档存在与访问权限
    # 检查现有锁
    existing_lock = session.exec(
        select(KnowledgeEditLock).where(KnowledgeEditLock.doc_id == doc_id)
    ).first()
    if existing_lock:
        if existing_lock.user_id == user.id:
            # 续租
            existing_lock.expires_at = datetime.utcnow() + timedelta(minutes=30)
            session.add(existing_lock)
            session.commit()
            return {"locked": True, "lockId": existing_lock.id}
        if existing_lock.expires_at > datetime.utcnow():
            # 锁仍有效
            lock_owner = session.get(User, existing_lock.user_id)
            owner_name = lock_owner.username if lock_owner else "未知用户"
            raise HTTPException(409, f"文档正在被 {owner_name} 编辑，请稍后再试")
        # 锁已过期，抢占
        session.delete(existing_lock)

    # 创建新锁
    lock = KnowledgeEditLock(
        doc_id=doc_id,
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    session.add(lock)
    session.commit()
    session.refresh(lock)
    return {"locked": True, "lockId": lock.id}


@router.post("/{doc_id}/unlock")
async def release_lock(
    doc_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    lock = session.exec(
        select(KnowledgeEditLock).where(KnowledgeEditLock.doc_id == doc_id)
    ).first()
    if not lock:
        return {"ok": True}
    if lock.user_id != user.id:
        raise HTTPException(403, "不是锁的持有者")
    session.delete(lock)
    session.commit()
    return {"ok": True}


# ---------- 协作者管理（P1-2 新增） ----------

@router.get("/{doc_id}/collaborators")
async def list_collaborators(
    doc_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    _get_doc_or_404(session, doc_id, user)  # 校验文档存在与访问权限
    collabs = session.exec(
        select(KnowledgeCollaborator).where(KnowledgeCollaborator.doc_id == doc_id)
    ).all()
    results = []
    for c in collabs:
        u = session.get(User, c.user_id)
        results.append({
            "id": c.id,
            "userId": c.user_id,
            "username": u.username if u else "未知用户",
            "permission": c.permission,
            "createdAt": c.created_at.isoformat() if c.created_at else None,
        })
    return results


@router.post("/{doc_id}/collaborators")
async def add_collaborator(
    doc_id: int,
    req: CollaboratorRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    doc = _get_doc_or_404(session, doc_id, user)
    if doc.user_id != user.id:
        raise HTTPException(403, "只有文档所有者可添加协作者")
    if req.permission not in ("read", "edit", "admin"):
        raise HTTPException(400, "无效的权限类型")
    # 检查是否已存在
    existing = session.exec(
        select(KnowledgeCollaborator).where(
            KnowledgeCollaborator.doc_id == doc_id,
            KnowledgeCollaborator.user_id == req.userId,
        )
    ).first()
    if existing:
        existing.permission = req.permission
        session.add(existing)
    else:
        collab = KnowledgeCollaborator(
            doc_id=doc_id,
            user_id=req.userId,
            permission=req.permission,
        )
        session.add(collab)
    session.commit()
    return {"ok": True}


@router.delete("/{doc_id}/collaborators/{collab_id}")
async def remove_collaborator(
    doc_id: int,
    collab_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    doc = _get_doc_or_404(session, doc_id, user)
    if doc.user_id != user.id:
        raise HTTPException(403, "只有文档所有者可移除协作者")
    collab = session.get(KnowledgeCollaborator, collab_id)
    if not collab or collab.doc_id != doc_id:
        raise HTTPException(404, "协作者不存在")
    session.delete(collab)
    session.commit()
    return {"ok": True}
