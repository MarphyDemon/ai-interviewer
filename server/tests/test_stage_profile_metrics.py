#! encoding=utf-8
"""面试状态机 / 跨会话画像 / 实测指标 的离线单元测试。

运行方式（不需要 LLM 与网络，使用临时 SQLite）：
    python server/tests/test_stage_profile_metrics.py
    python -m pytest server/tests/test_stage_profile_metrics.py -v   # 若装了 pytest

覆盖范围：
1. interview_stage：初始阶段、action→阶段映射、合法/非法转移、SSE 载荷
2. profile_service：报告 → 弱点聚合（含重复命中累加）、画像 prompt 文本、总览
3. metrics_service：落库、分位数聚合、工具排行、按面试明细
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sqlmodel import Session, SQLModel, create_engine, select  # noqa: E402

from server.models import (  # noqa: E402
    Interview,
    Report,
    User,
    UserWeaknessProfile,
)
from server.services import metrics_service, profile_service  # noqa: E402
from server.services.interview_stage import (  # noqa: E402
    STAGE_ALGORITHM,
    STAGE_ASK,
    STAGE_FINISHED,
    STAGE_OPENING,
    advance_by_action,
    advance_stage,
    can_transition,
    stage_from_action,
    stage_payload,
)


def _make_engine():
    path = os.path.join(tempfile.mkdtemp(prefix="ai-interviewer-test-"), "app.db")
    engine = create_engine(f"sqlite:///{path}")
    SQLModel.metadata.create_all(engine)
    return engine


def _seed(session: Session) -> Interview:
    user = User(anonymous_uuid="test-uuid", username="tester")
    session.add(user)
    session.commit()
    session.refresh(user)

    interview = Interview(user_id=user.id, position="后端", difficulty="中级")
    session.add(interview)
    session.commit()
    session.refresh(interview)
    return interview


# ---------- 1. 状态机 ----------


def test_stage_initial_and_action_mapping():
    assert stage_from_action("ask") == STAGE_ASK
    assert stage_from_action("next_question") == STAGE_ASK
    assert stage_from_action("algorithm") == STAGE_ALGORITHM
    # choices 等不改变阶段的 action 不应映射到任何阶段
    assert stage_from_action("choices") is None
    assert stage_from_action(None) is None
    payload = stage_payload(STAGE_OPENING)
    assert payload["stage"] == STAGE_OPENING
    assert payload["index"] == 1
    assert payload["total"] == 7
    assert payload["label"] == "开场"


def test_stage_transitions_and_guards():
    engine = _make_engine()
    with Session(engine) as session:
        interview = _seed(session)
        # 新建面试默认处于开场
        assert interview.stage == STAGE_OPENING

        # 开场 → 提问（按 action）
        assert advance_by_action(session, interview, "ask") is True
        assert interview.stage == STAGE_ASK
        assert interview.stage_updated_at is not None

        # 幂等：同阶段重复推进返回 False
        assert advance_by_action(session, interview, "ask") is False

        # 合法：提问 → 算法题
        assert advance_stage(session, interview, STAGE_ALGORITHM) is True
        assert interview.stage == STAGE_ALGORITHM

        # 非法：算法题 → 开场（转移表未允许）
        assert can_transition(STAGE_ALGORITHM, STAGE_OPENING) is False
        assert advance_stage(session, interview, STAGE_OPENING) is False
        assert interview.stage == STAGE_ALGORITHM

        # 强制收敛：允许跳入已结束
        assert advance_stage(session, interview, STAGE_FINISHED, force=True) is True
        assert interview.stage == STAGE_FINISHED
        # 终态不可再转移
        assert advance_stage(session, interview, STAGE_ASK) is False


# ---------- 2. 跨会话画像 ----------


def _weak_report(interview: Interview, score: float = 40.0) -> Report:
    return Report(
        interview_id=interview.id,
        total_score=55,
        dimension_scores=json.dumps(
            [
                {"label": "Technical Knowledge", "score": 80},
                {"label": "Communication", "score": 45},
            ],
            ensure_ascii=False,
        ),
        summary="总体一般",
        per_question_reviews=json.dumps(
            [
                {
                    "question": "索引失效的常见原因有哪些？",
                    "answer": "不太清楚",
                    "review": "对最左前缀原则理解不足",
                    "score": score,
                },
                {"question": "简单题", "answer": "答得不错", "review": "ok", "score": 90},
            ],
            ensure_ascii=False,
        ),
    )


def test_profile_aggregation_and_prompt():
    engine = _make_engine()
    with Session(engine) as session:
        interview = _seed(session)
        report = _weak_report(interview)
        session.add(report)
        session.commit()
        session.refresh(report)

        touched = profile_service.refresh_profile_from_report(session, interview, report)
        # 1 条知识点弱点 + 1 条表达维度弱点
        assert touched == 2

        weaknesses = profile_service.get_weaknesses(session, interview.user_id)
        assert len(weaknesses) == 2
        topics = {w["topic"] for w in weaknesses}
        assert "索引失效的常见原因有哪些？" in topics
        assert "Communication" in topics
        categories = {w["category"] for w in weaknesses}
        assert categories == {"knowledge", "expression"}

        # 第二场同样薄弱点 → hit_count 累加
        second = Interview(user_id=interview.user_id, position="后端", difficulty="中级")
        session.add(second)
        session.commit()
        session.refresh(second)
        second_report = _weak_report(second)
        session.add(second_report)
        session.commit()
        session.refresh(second_report)
        profile_service.refresh_profile_from_report(session, second, second_report)

        weaknesses = profile_service.get_weaknesses(session, interview.user_id)
        top = next(w for w in weaknesses if w["topic"] == "索引失效的常见原因有哪些？")
        assert top["hitCount"] == 2, top

        context = profile_service.build_profile_context(session, interview.user_id, "后端")
        assert "候选人历史画像" in context
        assert "索引失效" in context
        assert "平均总分" in context

        overview = profile_service.summary(session, interview.user_id)
        assert overview["reportCount"] == 2
        assert overview["weaknessCount"] == 2
        assert overview["categoryStats"]

        # 无数据的用户不应报错
        empty = User(anonymous_uuid="empty-uuid")
        session.add(empty)
        session.commit()
        session.refresh(empty)
        assert profile_service.build_profile_context(session, empty.id, "后端") == ""


def test_profile_table_used():
    engine = _make_engine()
    with Session(engine) as session:
        interview = _seed(session)
        report = _weak_report(interview)
        session.add(report)
        session.commit()
        session.refresh(report)
        profile_service.refresh_profile_from_report(session, interview, report)
        rows = session.exec(select(UserWeaknessProfile)).all()
        assert len(rows) >= 1


# ---------- 3. 实测指标 ----------


def test_metrics_record_and_summary():
    engine = _make_engine()
    with Session(engine) as session:
        interview = _seed(session)
        user_id = interview.user_id

        metrics_service.record_metrics(
            session,
            interview.id,
            user_id,
            [
                {"kind": "ttfa", "valueMs": 900},
                {"kind": "ttfa", "valueMs": 1200},
                {"kind": "e2e", "valueMs": 5000},
                {"kind": "tool", "valueMs": 800, "name": "run_code"},
                {"kind": "tool", "valueMs": 1200, "name": "run_code"},
                {"kind": "tool", "valueMs": 300, "name": "retrieve_knowledge"},
                {"kind": "unknown_kind", "valueMs": 1},
            ],
        )

        data = metrics_service.summary(session, days=30, user_id=user_id)
        assert data["interviewCount"] == 1
        # 非法 kind 被丢弃：2 ttfa + 1 e2e + 3 tool
        assert data["metricCount"] == 6
        assert data["kinds"]["ttfa"]["count"] == 2
        assert data["kinds"]["ttfa"]["avg"] == 1050
        assert data["kinds"]["tool"]["count"] == 3
        assert data["kinds"]["interrupt"]["count"] == 0
        assert data["kindLabels"]["ttfa"] == "首字延迟"

        top = data["toolTop"][0]
        assert top["name"] == "run_code"
        assert top["count"] == 2
        assert top["avg"] == 1000

        # 客户端上报（打断延迟）
        metrics_service.record_metric(session, interview.id, user_id, "interrupt", 420)
        data = metrics_service.summary(session, days=30, user_id=user_id)
        assert data["kinds"]["interrupt"]["avg"] == 420

        rows = metrics_service.interviews(session, limit=10, user_id=user_id)
        assert len(rows) == 1
        assert rows[0]["ttfaMs"] == 1050
        assert rows[0]["interruptMs"] == 420
        assert rows[0]["toolCalls"] == 3
        assert rows[0]["stage"] == STAGE_OPENING


def test_metrics_isolated_per_user():
    engine = _make_engine()
    with Session(engine) as session:
        first = _seed(session)
        other = User(anonymous_uuid="other-uuid")
        session.add(other)
        session.commit()
        session.refresh(other)
        second = Interview(user_id=other.id, position="前端", difficulty="初级")
        session.add(second)
        session.commit()
        session.refresh(second)

        metrics_service.record_metric(session, first.id, first.user_id, "ttfa", 100)
        metrics_service.record_metric(session, second.id, other.id, "ttfa", 200)

        mine = metrics_service.summary(session, days=30, user_id=first.user_id)
        assert mine["kinds"]["ttfa"]["avg"] == 100
        assert mine["interviewCount"] == 1

        everything = metrics_service.summary(session, days=30, user_id=None)
        assert everything["interviewCount"] == 2


# ---------- 运行入口 ----------

TESTS = [
    test_stage_initial_and_action_mapping,
    test_stage_transitions_and_guards,
    test_profile_aggregation_and_prompt,
    test_profile_table_used,
    test_metrics_record_and_summary,
    test_metrics_isolated_per_user,
]


def run_all() -> bool:
    passed, failed = 0, 0
    for func in TESTS:
        try:
            func()
            print(f"[PASS] {func.__name__}")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            import traceback

            print(f"[FAIL] {func.__name__}: {exc}")
            traceback.print_exc()
            failed += 1
    print(f"\n共 {len(TESTS)} 项：通过 {passed}，失败 {failed}")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run_all() else 1)
