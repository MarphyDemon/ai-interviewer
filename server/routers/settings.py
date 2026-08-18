import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session
from server.database import get_session
from server.models import User, UserQuota, Notification
from server.services.auth_service import get_current_user

router = APIRouter(prefix="/api/settings", tags=["settings"])


class PersonalSettingsUpdate(BaseModel):
    preferredAvatarConfigId: int | None = None
    preferredPosition: str | None = None
    language: str | None = None
    theme: str | None = None
    notificationSettings: dict | None = None


@router.get("/personal")
async def get_personal_settings(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    notif = {}
    if user.notification_settings:
        try:
            notif = json.loads(user.notification_settings)
        except Exception:
            notif = {}
    quota = session.exec(select(UserQuota).where(UserQuota.user_id == user.id)).first()
    return {
        "preferredAvatarConfigId": user.preferred_avatar_config_id,
        "preferredPosition": user.preferred_position,
        "language": user.language,
        "theme": user.theme,
        "notificationSettings": notif,
        "quota": {
            "plan": quota.plan if quota else "free",
            "interviewLimit": quota.interview_limit if quota else 10,
            "interviewUsed": quota.interview_used if quota else 0,
            "knowledgeLimit": quota.knowledge_limit if quota else 20,
            "knowledgeUsed": quota.knowledge_used if quota else 0,
            "aiCallsLimit": quota.ai_calls_limit if quota else 100,
            "aiCallsUsed": quota.ai_calls_used if quota else 0,
        } if quota or True else None,
    }


@router.put("/personal")
async def update_personal_settings(
    req: PersonalSettingsUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    if req.preferredAvatarConfigId is not None:
        user.preferred_avatar_config_id = req.preferredAvatarConfigId
    if req.preferredPosition is not None:
        user.preferred_position = req.preferredPosition
    if req.language is not None:
        user.language = req.language
    if req.theme is not None:
        user.theme = req.theme
    if req.notificationSettings is not None:
        user.notification_settings = json.dumps(req.notificationSettings, ensure_ascii=False)
    session.add(user)
    session.commit()
    return {"ok": True}


@router.get("/notifications")
async def list_notifications(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    notifications = session.exec(
        select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc())
    ).all()
    return [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "content": n.content,
            "isRead": n.is_read,
            "createdAt": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifications
    ]


@router.post("/notifications/{nid}/read")
async def mark_notification_read(
    nid: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    notif = session.get(Notification, nid)
    if not notif or notif.user_id != user.id:
        raise HTTPException(404, "通知不存在")
    notif.is_read = True
    session.add(notif)
    session.commit()
    return {"ok": True}


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    notifications = session.exec(
        select(Notification).where(Notification.user_id == user.id, Notification.is_read == False)
    ).all()
    for n in notifications:
        n.is_read = True
        session.add(n)
    session.commit()
    return {"ok": True, "count": len(notifications)}