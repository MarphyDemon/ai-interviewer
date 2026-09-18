import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlmodel import Session, or_, select
from server.database import get_session
from server.models import JobDescription, User
from server.services import org_service
from server.services.jd_service import parse_jd_file
from server.services.auth_service import get_current_user
from server.config import settings

router = APIRouter(prefix="/api/jd", tags=["jd"])

# 资源作用域：personal=个人私有；org=企业组织共享（同组织成员可见）
SCOPE_PERSONAL = "personal"
SCOPE_ORG = "org"


def _resolve_org_scope(session: Session, user: User, scope: str) -> int | None:
    """把 scope 解析为 org_id。scope=org 要求用户属于某个组织且具备管理角色。"""
    if scope != SCOPE_ORG:
        return None
    org_id = org_service.user_org_id(session, user.id)
    if not org_id:
        raise HTTPException(403, "当前账号未加入任何企业组织，无法创建组织共享 JD")
    if not org_service.can_manage_invite(session, user, org_id):
        raise HTTPException(403, "需要组织管理员权限（owner / hr）")
    return org_id


def _visible_jds(session: Session, user: User) -> list[JobDescription]:
    """可见 JD：本人创建的 ∪ 所在组织共享的。"""
    conditions = [JobDescription.user_id == user.id]
    org_id = org_service.user_org_id(session, user.id)
    if org_id:
        conditions.append(JobDescription.org_id == org_id)
    return list(
        session.exec(
            select(JobDescription)
            .where(or_(*conditions))
            .order_by(JobDescription.created_at.desc())
        ).all()
    )


@router.get("")
async def list_jds(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return [_format_jd(j) for j in _visible_jds(session, user)]


@router.get("/{jd_id}")
async def get_jd(
    jd_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    jd = session.get(JobDescription, jd_id)
    if not jd or not org_service.can_view_org_resource(session, user, jd.user_id, jd.org_id):
        raise HTTPException(404, "Job description not found")
    return _format_jd(jd)


@router.post("")
async def create_jd(
    title: str = Form(...),
    content: str = Form(...),
    position: str = Form(""),
    scope: str = Form(SCOPE_PERSONAL),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    jd = JobDescription(
        user_id=user.id,
        org_id=_resolve_org_scope(session, user, scope),
        title=title.strip() or "未命名 JD",
        content=content,
        position=position,
    )
    session.add(jd)
    session.commit()
    session.refresh(jd)
    return _format_jd(jd)


@router.post("/upload")
async def upload_jd(
    file: UploadFile = File(...),
    title: str = Form(""),
    position: str = Form(""),
    scope: str = Form(SCOPE_PERSONAL),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".pdf", ".docx", ".md", ".markdown", ".txt"):
        raise HTTPException(400, "Only PDF, DOCX, Markdown and TXT are supported")

    org_id = _resolve_org_scope(session, user, scope)

    os.makedirs(settings.data_dir / "jds", exist_ok=True)
    saved_name = f"{uuid.uuid4().hex}{ext}"
    file_path = settings.data_dir / "jds" / saved_name

    content_bytes = await file.read()
    with open(file_path, "wb") as f:
        f.write(content_bytes)

    parsed_text = parse_jd_file(str(file_path))
    os.remove(file_path)

    if not parsed_text.strip():
        raise HTTPException(400, "无法从文件中提取文本，请检查文件内容")

    jd = JobDescription(
        user_id=user.id,
        org_id=org_id,
        title=title.strip() or os.path.splitext(file.filename)[0] or "未命名 JD",
        content=parsed_text,
        position=position,
    )
    session.add(jd)
    session.commit()
    session.refresh(jd)
    return _format_jd(jd)


@router.put("/{jd_id}")
async def update_jd(
    jd_id: int,
    title: str = Form(None),
    content: str = Form(None),
    position: str = Form(None),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    jd = session.get(JobDescription, jd_id)
    if not jd or not org_service.can_manage_org_resource(session, user, jd.user_id, jd.org_id):
        raise HTTPException(404, "Job description not found")
    if title is not None:
        jd.title = title.strip() or jd.title
    if content is not None:
        jd.content = content
    if position is not None:
        jd.position = position
    jd.updated_at = datetime.utcnow()
    session.add(jd)
    session.commit()
    session.refresh(jd)
    return _format_jd(jd)


@router.delete("/{jd_id}")
async def delete_jd(
    jd_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    jd = session.get(JobDescription, jd_id)
    if not jd or not org_service.can_manage_org_resource(session, user, jd.user_id, jd.org_id):
        raise HTTPException(404, "Job description not found")
    session.delete(jd)
    session.commit()
    return {"ok": True}


def _format_jd(jd: JobDescription) -> dict:
    return {
        "id": jd.id,
        "title": jd.title,
        "content": jd.content,
        "position": jd.position,
        # orgId 非空表示这是企业组织共享的 JD
        "orgId": jd.org_id,
        "createdAt": jd.created_at.isoformat() if jd.created_at else None,
        "updatedAt": jd.updated_at.isoformat() if jd.updated_at else None,
    }
