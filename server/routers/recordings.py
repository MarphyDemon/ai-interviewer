"""面试回放录制服务。

设计说明：
- MVP 使用 MediaRecorder API 录制音频/视频，上传到后端存储。
- 录制文件通过 storage_service 保存（本地 / S3 均可）。
- 回放时通过 /api/recordings/{id}/stream 端点流式播放。
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session, select

from server.database import get_session
from server.models import Recording, User, Interview
from server.services.auth_service import get_current_user
from server.services.storage_service import storage

router = APIRouter(prefix="/api/recordings", tags=["recordings"])


@router.post("/upload/{interview_id}")
async def upload_recording(
    interview_id: int,
    stream_type: str = "audio",
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """上传录制文件（面试中的音频/视频片段）。"""
    interview = session.get(Interview, interview_id)
    if not interview or interview.user_id != user.id:
        raise HTTPException(404, "面试不存在")

    content = await file.read()
    ext = ".webm"  # MediaRecorder 默认输出格式
    file_key = f"recordings/{interview_id}/{uuid.uuid4().hex}{ext}"

    url = await storage.save(
        file_key,
        content,
        content_type=file.content_type or "audio/webm",
    )

    recording = Recording(
        interview_id=interview_id,
        user_id=user.id,
        stream_type=stream_type,
        file_key=file_key,
        file_size=len(content),
        mime_type=file.content_type or "audio/webm",
    )
    session.add(recording)
    session.commit()
    session.refresh(recording)

    return {
        "id": recording.id,
        "url": url,
        "fileSize": recording.file_size,
        "mimeType": recording.mime_type,
    }


@router.get("/{interview_id}")
async def list_recordings(
    interview_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """获取某场面试的所有录制文件列表。"""
    interview = session.get(Interview, interview_id)
    if not interview or interview.user_id != user.id:
        raise HTTPException(404, "面试不存在")

    recordings = session.exec(
        select(Recording).where(Recording.interview_id == interview_id)
    ).all()

    return [
        {
            "id": r.id,
            "streamType": r.stream_type,
            "fileSize": r.file_size,
            "durationMs": r.duration_ms,
            "mimeType": r.mime_type,
            "url": storage.get_url(r.file_key),
            "createdAt": r.created_at.isoformat() if r.created_at else None,
        }
        for r in recordings
    ]


@router.get("/{interview_id}/stream/{recording_id}")
async def stream_recording(
    interview_id: int,
    recording_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """流式播放录制文件。"""
    interview = session.get(Interview, interview_id)
    if not interview or interview.user_id != user.id:
        raise HTTPException(404, "面试不存在")

    recording = session.get(Recording, recording_id)
    if not recording or recording.interview_id != interview_id:
        raise HTTPException(404, "录制文件不存在")

    data = await storage.read(recording.file_key)
    if data is None:
        raise HTTPException(404, "文件不存在")

    from fastapi.responses import Response
    return Response(
        content=data,
        media_type=recording.mime_type or "audio/webm",
        headers={
            "Content-Disposition": f"inline; filename=recording_{recording_id}.webm",
            "Accept-Ranges": "bytes",
        },
    )


@router.delete("/{interview_id}/{recording_id}")
async def delete_recording(
    interview_id: int,
    recording_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """删除录制文件。"""
    interview = session.get(Interview, interview_id)
    if not interview or interview.user_id != user.id:
        raise HTTPException(404, "面试不存在")

    recording = session.get(Recording, recording_id)
    if not recording or recording.interview_id != interview_id:
        raise HTTPException(404, "录制文件不存在")

    await storage.delete(recording.file_key)
    session.delete(recording)
    session.commit()
    return {"ok": True}