import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlmodel import Session, select
from server.database import get_session
from server.models import JobDescription, User
from server.services.jd_service import parse_jd_file
from server.services.auth_service import get_current_user
from server.config import settings

router = APIRouter(prefix="/api/jd", tags=["jd"])


@router.get("")
async def list_jds(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    jds = session.exec(
        select(JobDescription)
        .where(JobDescription.user_id == user.id)
        .order_by(JobDescription.created_at.desc())
    ).all()
    return [_format_jd(j) for j in jds]


@router.get("/{jd_id}")
async def get_jd(
    jd_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    jd = session.get(JobDescription, jd_id)
    if not jd or jd.user_id != user.id:
        raise HTTPException(404, "Job description not found")
    return _format_jd(jd)


@router.post("")
async def create_jd(
    title: str = Form(...),
    content: str = Form(...),
    position: str = Form(""),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    jd = JobDescription(
        user_id=user.id,
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
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".pdf", ".docx", ".md", ".markdown", ".txt"):
        raise HTTPException(400, "Only PDF, DOCX, Markdown and TXT are supported")

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
    if not jd or jd.user_id != user.id:
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
    if not jd or jd.user_id != user.id:
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
        "createdAt": jd.created_at.isoformat() if jd.created_at else None,
        "updatedAt": jd.updated_at.isoformat() if jd.updated_at else None,
    }
