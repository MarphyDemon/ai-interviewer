"""跨会话候选人画像接口（弱点 / 平均分 / 分类统计）。"""

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from server.database import get_session
from server.models import User
from server.services.auth_service import get_current_user
from server.services.profile_service import summary as profile_summary

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("/summary")
def get_profile_summary(
    limit: int = Query(8, ge=1, le=50),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """当前用户的面试画像：往期场次、平均分、反复出现的薄弱点。"""
    return profile_summary(session, user.id, limit=limit)
