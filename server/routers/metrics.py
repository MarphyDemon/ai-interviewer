"""实测指标接口：/metrics 页面的数据源。

数据来源见 `server/services/metrics_service.py`：
- 服务端自动埋点（首字延迟 / 工具耗时 / 端到端）
- 客户端上报（打断延迟，前端测量 `interrupt()` 的耗时）

权限：读取类接口（summary / interviews）为平台级数据，仅超管可用；
上报类接口（interview/{id}）所有登录用户可用，前端在面试中上报打断延迟。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from server.database import get_session
from server.models import Interview, User
from server.services.auth_service import get_current_user, require_admin
from server.services.metrics_service import (
    METRIC_KINDS,
    interviews as list_interviews,
    record_metric,
    summary as metrics_summary,
)

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


class MetricReport(BaseModel):
    kind: str
    valueMs: int
    name: str = ""


def _scope_user_id(user: User, scope: str):
    """scope=me 只看自己，其余（默认 all）看全站。

    读取类接口已由 require_admin 限制为超管，因此默认给全站数据，
    否则管理员进页面只能看到自己那几场，指标页没有意义。
    """
    return user.id if scope == "me" else None


@router.get("/summary")
def get_summary(
    days: int = Query(30, ge=1, le=365),
    scope: str = Query("all"),
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    return metrics_summary(session, days=days, user_id=_scope_user_id(user, scope))


@router.get("/interviews")
def get_interview_metrics(
    limit: int = Query(50, ge=1, le=200),
    scope: str = Query("all"),
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    return list_interviews(session, limit=limit, user_id=_scope_user_id(user, scope))


@router.post("/interview/{interview_id}")
def report_client_metric(
    interview_id: int,
    req: MetricReport,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """前端上报客户端侧指标（目前用于打断延迟）。"""
    interview = session.get(Interview, interview_id)
    if not interview or interview.user_id != user.id:
        raise HTTPException(404, "Interview not found")
    if req.kind not in METRIC_KINDS:
        raise HTTPException(400, f"未知指标类型：{req.kind}")

    record_metric(session, interview_id, user.id, req.kind, req.valueMs, req.name)
    return {"ok": True}
