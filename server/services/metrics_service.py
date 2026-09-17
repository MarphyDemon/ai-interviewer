"""面试实测指标：落库与聚合。

指标来源：
- 服务端：brain 链路每轮产出 ttfa（首字延迟）/ tool（单次工具耗时）/ e2e（端到端），
  落库点在 `interview_brain_service.generate_interview_stream`。
- 客户端：打断延迟（`interrupt()` 从调用到结束的耗时）由前端上报
  `POST /api/metrics/interview/{id}`。

聚合结果供 `/metrics` 页面展示真实实测数据（赛题要求「公开实测值」）。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Session, select

from server.models import Interview, InterviewMetric

METRIC_KINDS: tuple[str, ...] = ("ttfa", "tool", "e2e", "interrupt")

KIND_LABELS: dict[str, str] = {
    "ttfa": "首字延迟",
    "tool": "工具耗时",
    "e2e": "端到端耗时",
    "interrupt": "打断延迟",
}


def record_metric(
    session: Session,
    interview_id: int,
    user_id: int,
    kind: str,
    value_ms: int,
    name: str = "",
) -> None:
    """记录单条指标；任何异常都不应影响面试主流程。"""
    if kind not in METRIC_KINDS or value_ms is None or value_ms < 0:
        return
    try:
        session.add(
            InterviewMetric(
                interview_id=interview_id,
                user_id=user_id,
                kind=kind,
                name=name or "",
                value_ms=int(value_ms),
            )
        )
        session.commit()
    except Exception as e:  # 指标属于旁路，失败不阻断面试
        session.rollback()
        print(f"[Metrics] record failed ({kind}): {e}")


def record_metrics(
    session: Session,
    interview_id: int,
    user_id: int,
    items: list[dict],
) -> None:
    """批量记录指标。items: [{kind, valueMs, name}]"""
    rows = []
    for item in items or []:
        kind = item.get("kind")
        value = item.get("valueMs", item.get("value_ms"))
        if kind not in METRIC_KINDS or value is None:
            continue
        try:
            rows.append(
                InterviewMetric(
                    interview_id=interview_id,
                    user_id=user_id,
                    kind=str(kind),
                    name=str(item.get("name") or ""),
                    value_ms=int(value),
                )
            )
        except (TypeError, ValueError):
            continue
    if not rows:
        return
    try:
        session.add_all(rows)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"[Metrics] batch record failed: {e}")


def _percentiles(values: list[int]) -> dict:
    """返回 avg / p50 / p95 / max / count（样本量小时分位数按最近秩取）。"""
    if not values:
        return {"avg": None, "p50": None, "p95": None, "max": None, "count": 0}
    ordered = sorted(values)

    def _pick(ratio: float) -> int:
        idx = min(len(ordered) - 1, max(0, int(round(ratio * (len(ordered) - 1)))))
        return ordered[idx]

    return {
        "avg": round(sum(ordered) / len(ordered)),
        "p50": _pick(0.5),
        "p95": _pick(0.95),
        "max": ordered[-1],
        "count": len(ordered),
    }


def _load_metrics(session: Session, days: int, user_id: Optional[int]) -> list[InterviewMetric]:
    cutoff = datetime.utcnow() - timedelta(days=max(1, days))
    stmt = select(InterviewMetric).where(InterviewMetric.created_at >= cutoff)
    if user_id is not None:
        stmt = stmt.where(InterviewMetric.user_id == user_id)
    return list(session.exec(stmt).all())


def summary(session: Session, days: int = 30, user_id: Optional[int] = None) -> dict:
    """按指标类型聚合（均值 + p50 + p95 + 最大值 + 样本数），并给出工具耗时排行。"""
    rows = _load_metrics(session, days, user_id)

    by_kind: dict[str, list[int]] = {kind: [] for kind in METRIC_KINDS}
    by_tool: dict[str, list[int]] = {}
    interview_ids: set[int] = set()

    for row in rows:
        interview_ids.add(row.interview_id)
        if row.kind in by_kind:
            by_kind[row.kind].append(row.value_ms)
        if row.kind == "tool" and row.name:
            by_tool.setdefault(row.name, []).append(row.value_ms)

    tool_top = [
        {"name": name, "count": len(values), **_percentiles(values)}
        for name, values in by_tool.items()
    ]
    tool_top.sort(key=lambda item: (item["count"], item["avg"] or 0), reverse=True)

    return {
        "days": days,
        "interviewCount": len(interview_ids),
        "metricCount": len(rows),
        "kinds": {kind: _percentiles(by_kind[kind]) for kind in METRIC_KINDS},
        "kindLabels": KIND_LABELS,
        "toolTop": tool_top[:10],
    }


def _avg(values: list[int]) -> Optional[int]:
    return round(sum(values) / len(values)) if values else None


def interviews(session: Session, limit: int = 50, user_id: Optional[int] = None) -> list[dict]:
    """每次面试的指标明细（用于表格展示与导出）。"""
    size = max(1, min(limit, 200))
    stmt = select(Interview).order_by(Interview.started_at.desc()).limit(size)
    if user_id is not None:
        stmt = (
            select(Interview)
            .where(Interview.user_id == user_id)
            .order_by(Interview.started_at.desc())
            .limit(size)
        )
    interview_rows = list(session.exec(stmt).all())
    if not interview_rows:
        return []

    ids = [i.id for i in interview_rows if i.id]
    metric_rows = list(
        session.exec(select(InterviewMetric).where(InterviewMetric.interview_id.in_(ids))).all()
    )
    grouped: dict[int, dict[str, list[int]]] = {i: {} for i in ids}
    for row in metric_rows:
        if row.interview_id not in grouped:
            continue
        grouped[row.interview_id].setdefault(row.kind, []).append(row.value_ms)

    result = []
    for interview in interview_rows:
        buckets = grouped.get(interview.id, {})
        tool_values = buckets.get("tool") or []
        result.append(
            {
                "interviewId": interview.id,
                "position": interview.position,
                "difficulty": interview.difficulty,
                "stage": interview.stage,
                "status": interview.status,
                "startedAt": interview.started_at.isoformat() if interview.started_at else None,
                "ttfaMs": _avg(buckets.get("ttfa") or []),
                "toolMs": _avg(tool_values),
                "e2eMs": _avg(buckets.get("e2e") or []),
                "interruptMs": _avg(buckets.get("interrupt") or []),
                "toolCalls": len(tool_values),
            }
        )
    return result
