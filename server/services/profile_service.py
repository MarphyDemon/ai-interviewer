"""跨会话候选人弱点画像。

问题背景：此前每场面试都是「从零开始」——报告里有逐题点评，但不会回流到下一场面试，
候选人反复暴露的同一个弱点在下一场仍然不会被针对。

本模块把每场报告聚合为结构化画像（UserWeaknessProfile），并在下一场面试的
system prompt 中注入，使面试官能「记得」候选人上次哪里薄弱。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from server.models import Interview, Report, UserWeaknessProfile

# 判定阈值
WEAK_QUESTION_SCORE = 60.0
WEAK_DIMENSION_SCORE = 70.0

CATEGORY_LABELS: dict[str, str] = {
    "knowledge": "知识点",
    "expression": "表达",
    "logic": "逻辑",
    "jobfit": "岗位匹配",
}

# 报告维度标签（中英）→ 画像分类
_DIMENSION_CATEGORY: dict[str, str] = {
    "technical knowledge": "knowledge",
    "technical depth": "knowledge",
    "problem solving": "logic",
    "communication": "expression",
    "job fit": "jobfit",
    "技术知识": "knowledge",
    "技术深度": "knowledge",
    "解决问题": "logic",
    "沟通表达": "expression",
    "表达力": "expression",
    "逻辑性": "logic",
    "人岗匹配": "jobfit",
}

_TOPIC_MAX_LEN = 40


def _parse_json(raw: Optional[str], fallback):
    try:
        return json.loads(raw) if raw else fallback
    except (json.JSONDecodeError, TypeError):
        return fallback


def _topic_of(text: Optional[str]) -> str:
    """把题目/点评压成可聚合的话题名（去换行、去 Markdown 标记、限长）。"""
    if not text:
        return ""
    cleaned = " ".join(str(text).replace("*", " ").replace("#", " ").split())
    return cleaned[:_TOPIC_MAX_LEN]


def _upsert(
    session: Session,
    user_id: int,
    position: str,
    category: str,
    topic: str,
    score: float,
    severity: float,
    evidence: str,
    interview_id: Optional[int],
) -> None:
    if not topic:
        return
    existing = session.exec(
        select(UserWeaknessProfile).where(
            UserWeaknessProfile.user_id == user_id,
            UserWeaknessProfile.position == position,
            UserWeaknessProfile.category == category,
            UserWeaknessProfile.topic == topic,
        )
    ).first()

    now = datetime.utcnow()
    if existing:
        existing.hit_count += 1
        existing.severity = max(existing.severity, severity)
        existing.latest_score = score
        existing.evidence = evidence or existing.evidence
        existing.last_interview_id = interview_id
        existing.updated_at = now
        session.add(existing)
    else:
        session.add(
            UserWeaknessProfile(
                user_id=user_id,
                position=position,
                category=category,
                topic=topic,
                hit_count=1,
                severity=severity,
                latest_score=score,
                evidence=evidence,
                last_interview_id=interview_id,
            )
        )


def refresh_profile_from_report(session: Session, interview: Interview, report: Report) -> int:
    """一场面试结束（报告生成）后刷新画像，返回新增/更新的弱点条数。"""
    user_id = interview.user_id
    if not user_id or not report:
        return 0

    position = interview.position or ""
    touched = 0

    # 1) 逐题点评中得分偏低的题 → 知识点弱点
    reviews = _parse_json(report.per_question_reviews, [])
    if isinstance(reviews, list):
        for item in reviews:
            if not isinstance(item, dict):
                continue
            try:
                score = float(item.get("score") or 0)
            except (TypeError, ValueError):
                continue
            if score >= WEAK_QUESTION_SCORE:
                continue
            topic = _topic_of(item.get("question"))
            if not topic:
                continue
            _upsert(
                session,
                user_id,
                position,
                "knowledge",
                topic,
                score,
                WEAK_QUESTION_SCORE - score,
                _topic_of(item.get("review"))[:200],
                interview.id,
            )
            touched += 1

    # 2) 维度得分最低且偏低的一项 → 表达/逻辑/岗位匹配弱点
    dimensions = _parse_json(report.dimension_scores, [])
    weakest: Optional[tuple[str, float]] = None
    if isinstance(dimensions, list):
        for dim in dimensions:
            if not isinstance(dim, dict):
                continue
            try:
                score = float(dim.get("score") or 0)
            except (TypeError, ValueError):
                continue
            label = str(dim.get("label") or "").strip()
            if not label:
                continue
            if weakest is None or score < weakest[1]:
                weakest = (label, score)

    if weakest and weakest[1] < WEAK_DIMENSION_SCORE:
        label, score = weakest
        category = _DIMENSION_CATEGORY.get(label.lower(), "knowledge")
        _upsert(
            session,
            user_id,
            position,
            category,
            _topic_of(label),
            score,
            WEAK_DIMENSION_SCORE - score,
            f"最近一场该维度得分 {score:.0f}",
            interview.id,
        )
        touched += 1

    if touched:
        session.commit()
    return touched


def get_weaknesses(
    session: Session,
    user_id: int,
    position: Optional[str] = None,
    limit: int = 8,
) -> list[dict]:
    """按「出现次数 → 严重度」排序返回弱点列表。"""
    stmt = select(UserWeaknessProfile).where(UserWeaknessProfile.user_id == user_id)
    if position:
        stmt = stmt.where(UserWeaknessProfile.position == position)
    rows = list(session.exec(stmt).all())
    rows.sort(key=lambda r: (r.hit_count, r.severity), reverse=True)
    return [
        {
            "topic": r.topic,
            "category": r.category,
            "categoryLabel": CATEGORY_LABELS.get(r.category, r.category),
            "hitCount": r.hit_count,
            "severity": round(r.severity, 1),
            "latestScore": round(r.latest_score, 1),
            "evidence": r.evidence,
            "position": r.position,
            "lastInterviewId": r.last_interview_id,
        }
        for r in rows[: max(1, limit)]
    ]


def _user_reports(session: Session, user_id: int) -> tuple[int, Optional[float]]:
    """返回（已结束面试数, 平均总分）。"""
    interviews = list(session.exec(select(Interview).where(Interview.user_id == user_id)).all())
    ids = [i.id for i in interviews if i.id]
    if not ids:
        return 0, None
    reports = list(session.exec(select(Report).where(Report.interview_id.in_(ids))).all())
    scores = [r.total_score for r in reports if r.total_score]
    avg = round(sum(scores) / len(scores), 1) if scores else None
    return len(reports), avg


def build_profile_context(
    session: Session,
    user_id: Optional[int],
    position: Optional[str] = None,
    limit: int = 6,
) -> str:
    """构造注入 system prompt 的画像片段；无历史数据时返回空字符串。"""
    if not user_id:
        return ""

    weaknesses = get_weaknesses(session, user_id, position=position, limit=limit)
    report_count, avg_score = _user_reports(session, user_id)
    if not weaknesses and avg_score is None:
        return ""

    lines: list[str] = ["## 候选人历史画像（跨会话，来自往期面试报告）"]
    if avg_score is not None:
        lines.append(f"- 往期共 {report_count} 场，平均总分 {avg_score}/100")
    if weaknesses:
        lines.append("- 反复出现/最近暴露的薄弱点：")
        for item in weaknesses:
            lines.append(
                f"  · [{item['categoryLabel']}] {item['topic']}"
                f"（{item['hitCount']} 次，最近得分 {item['latestScore']}）"
            )
        lines.append(
            "使用要求：优先针对上述薄弱点提问与追问；若候选人本次明显改善，请在点评中说明进步。"
            "不要直接念出这份画像，也不要提及「历史数据」。"
        )
    else:
        lines.append("- 暂无明显薄弱点记录。")
    return "\n".join(lines) + "\n"


def summary(session: Session, user_id: int, limit: int = 8) -> dict:
    """画像总览（供前端展示）。"""
    report_count, avg_score = _user_reports(session, user_id)
    weaknesses = get_weaknesses(session, user_id, limit=limit)

    category_stats: dict[str, int] = {}
    for item in weaknesses:
        category_stats[item["category"]] = category_stats.get(item["category"], 0) + item["hitCount"]

    return {
        "reportCount": report_count,
        "avgScore": avg_score,
        "weaknessCount": len(weaknesses),
        "weaknesses": weaknesses,
        "categoryStats": [
            {"category": key, "label": CATEGORY_LABELS.get(key, key), "count": value}
            for key, value in sorted(category_stats.items(), key=lambda kv: kv[1], reverse=True)
        ],
    }
