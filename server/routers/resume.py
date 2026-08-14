import json
import os
import uuid
import io
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select
from server.database import get_session
from server.models import Resume, ResumeReport, User
from server.services.resume_service import (
    parse_resume_file,
    analyze_resume,
    generate_resume_report,
    get_resume_report,
)
from server.services.auth_service import get_current_user
from server.services.storage_service import storage
from server.config import settings
import asyncio

router = APIRouter(prefix="/api/resume", tags=["resume"])


@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    position: str = Form(""),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".pdf", ".docx"):
        raise HTTPException(400, "Only PDF and DOCX are supported")

    saved_name = f"resumes/{uuid.uuid4().hex}{ext}"

    content = await file.read()
    await storage.save(saved_name, content, content_type=file.content_type or "")

    # 本地临时文件路径供 parse_resume_file 使用（该函数需要文件路径）
    local_tmp = settings.data_dir / "resumes" / Path(saved_name).name
    with open(local_tmp, "wb") as f:
        f.write(content)

    parsed_text = parse_resume_file(str(local_tmp))

    analysis = await analyze_resume(parsed_text, position)

    resume = Resume(
        user_id=user.id,
        filename=file.filename,
        file_path=saved_name,  # 存储 key，通过 storage.get_url() 访问
        parsed_text=parsed_text,
        analysis_result=json.dumps(analysis, ensure_ascii=False),
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)

    return _format_resume(resume)


@router.get("")
async def list_resumes(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    resumes = session.exec(select(Resume).where(Resume.user_id == user.id)).all()
    return [_format_resume(r) for r in resumes]


@router.get("/{resume_id}")
async def get_resume(
    resume_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    resume = session.get(Resume, resume_id)
    if not resume or resume.user_id != user.id:
        raise HTTPException(404, "Resume not found")
    return _format_resume(resume)


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    resume = session.get(Resume, resume_id)
    if not resume or resume.user_id != user.id:
        raise HTTPException(404, "Resume not found")
    if os.path.exists(resume.file_path):
        os.remove(resume.file_path)
    session.delete(resume)
    session.commit()
    return {"ok": True}


class GenerateReportReq(BaseModel):
    position: str


@router.post("/{resume_id}/report")
async def generate_resume_report_api(
    resume_id: int,
    req: GenerateReportReq,
    session: Session = Depends(get_session),
):
    """生成（或刷新）简历深度评估报告"""
    resume = session.get(Resume, resume_id)
    if not resume:
        raise HTTPException(404, "Resume not found")
    if not req.position.strip():
        raise HTTPException(400, "position is required")

    report_data = await generate_resume_report(resume.parsed_text, req.position.strip())

    # 删除同简历同岗位的旧报告，保留最新一份
    old = get_resume_report(session, resume_id, req.position.strip())
    if old:
        session.delete(old)
        session.commit()

    new_report = ResumeReport(
        resume_id=resume_id,
        position=req.position.strip(),
        grade=report_data.get("grade", "B"),
        report_data=json.dumps(report_data, ensure_ascii=False),
    )
    session.add(new_report)
    session.commit()
    session.refresh(new_report)

    return _format_resume_report(new_report)


@router.get("/{resume_id}/report")
async def get_resume_report_api(
    resume_id: int,
    position: str,
    session: Session = Depends(get_session),
):
    """查询已有报告（按 resume_id + position）"""
    report = get_resume_report(session, resume_id, position)
    if not report:
        raise HTTPException(404, "Report not found, please generate first")
    return _format_resume_report(report)


@router.get("/{resume_id}/report/pdf")
async def export_resume_report_pdf(
    resume_id: int,
    position: str,
    session: Session = Depends(get_session),
):
    """导出简历报告 PDF"""
    report = get_resume_report(session, resume_id, position)
    if not report:
        raise HTTPException(404, "Report not found")

    from server.services.pdf_service import generate_resume_report_pdf

    pdf_bytes = generate_resume_report_pdf(
        _format_resume_report(report)
    )
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=resume_report_{resume_id}.pdf"
        },
    )


def _format_resume_report(r: ResumeReport) -> dict:
    data = json.loads(r.report_data) if r.report_data else {}
    return {
        "id": r.id,
        "resumeId": r.resume_id,
        "position": r.position,
        "grade": r.grade,
        "data": data,
        "createdAt": r.created_at.isoformat() if r.created_at else None,
    }


def _format_resume(r: Resume) -> dict:
    return {
        "id": r.id,
        "filename": r.filename,
        "parsedText": r.parsed_text,
        "analysisResult": json.loads(r.analysis_result) if r.analysis_result else {},
        "createdAt": r.created_at.isoformat() if r.created_at else None,
    }
