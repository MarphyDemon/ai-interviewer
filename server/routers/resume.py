import json
import os
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlmodel import Session, select
from server.database import get_session
from server.models import Resume
from server.services.resume_service import parse_resume_file, analyze_resume
from server.services.common import get_or_create_user
from server.config import settings
import asyncio

router = APIRouter(prefix="/api/resume", tags=["resume"])


@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    position: str = Form(""),
    session: Session = Depends(get_session),
):
    user_uuid = "default"
    user_id = get_or_create_user(session, user_uuid)

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".pdf", ".docx"):
        raise HTTPException(400, "Only PDF and DOCX are supported")

    saved_name = f"{uuid.uuid4().hex}{ext}"
    file_path = settings.data_dir / "resumes" / saved_name

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    parsed_text = parse_resume_file(str(file_path))

    analysis = await analyze_resume(parsed_text, position)

    resume = Resume(
        user_id=user_id,
        filename=file.filename,
        file_path=str(file_path),
        parsed_text=parsed_text,
        analysis_result=json.dumps(analysis, ensure_ascii=False),
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)

    return _format_resume(resume)


@router.get("")
async def list_resumes(session: Session = Depends(get_session)):
    resumes = session.exec(select(Resume)).all()
    return [_format_resume(r) for r in resumes]


@router.get("/{resume_id}")
async def get_resume(resume_id: int, session: Session = Depends(get_session)):
    resume = session.get(Resume, resume_id)
    if not resume:
        raise HTTPException(404, "Resume not found")
    return _format_resume(resume)


@router.delete("/{resume_id}")
async def delete_resume(resume_id: int, session: Session = Depends(get_session)):
    resume = session.get(Resume, resume_id)
    if not resume:
        raise HTTPException(404, "Resume not found")
    if os.path.exists(resume.file_path):
        os.remove(resume.file_path)
    session.delete(resume)
    session.commit()
    return {"ok": True}


def _format_resume(r: Resume) -> dict:
    return {
        "id": r.id,
        "filename": r.filename,
        "parsedText": r.parsed_text,
        "analysisResult": json.loads(r.analysis_result) if r.analysis_result else {},
        "createdAt": r.created_at.isoformat() if r.created_at else None,
    }
