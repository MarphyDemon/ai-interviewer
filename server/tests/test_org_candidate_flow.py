#! encoding=utf-8
"""企业侧（候选人初筛）离线单元测试：组织 / 邀请 / 候选人 / 权限 / 排名。

运行方式（不需要 LLM 与网络，使用临时 SQLite；首题生成被 mock 掉）：
    python server/tests/test_org_candidate_flow.py
    python -m pytest server/tests/test_org_candidate_flow.py -v   # 若装了 pytest

覆盖范围：
1. org_service：组织自助开通、成员角色、邀请生命周期（吊销/过期）
2. 候选人免注册：落库为无密码 User + Candidate 归属记录
3. 面试归属：start_interview_session 带 org_id 时归属组织，排名能查到该候选人
4. 权限矩阵：本人 / 组织成员 / 外部用户 / admin 对面试与报告的可见性
5. 排名排序：有报告按分数倒序，未出报告排最后
"""

import asyncio
import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sqlmodel import Session, SQLModel, create_engine, select  # noqa: E402

from server.models import (  # noqa: E402
    Candidate,
    Interview,
    Organization,
    Report,
    User,
)
from server.services import org_service  # noqa: E402
from server.services.interview_service import start_interview_session  # noqa: E402


def _make_engine():
    path = os.path.join(tempfile.mkdtemp(prefix="ai-interviewer-org-test-"), "app.db")
    engine = create_engine(f"sqlite:///{path}")
    SQLModel.metadata.create_all(engine)
    return engine


def _user(session: Session, username: str, role: str = "user") -> User:
    user = User(anonymous_uuid=uuid.uuid4().hex, username=username, role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


async def _fake_first_question(session, interview, resume=None, jd=None, lang="en"):
    """替掉真实 LLM 调用，返回一个固定的首个提问。"""
    return {"action": "ask", "content": "请先做个自我介绍。", "reasoning": "开场"}


# ---------- 1. 组织与成员 ----------


def test_org_auto_create_and_members():
    engine = _make_engine()
    with Session(engine) as session:
        hr = _user(session, "hr_boss")

        org = org_service.get_or_create_org(session, hr)
        assert org.id is not None
        assert org.owner_id == hr.id
        # 幂等：再次调用不会新建组织
        assert org_service.get_or_create_org(session, hr).id == org.id
        assert org_service.member_role(session, org.id, hr.id) == "owner"

        # 加入第二个 HR
        colleague = _user(session, "hr_two")
        org_service.add_member(session, org, "hr_two", role="hr")
        assert org_service.member_role(session, org.id, colleague.id) == "hr"
        # 重复加入不产生第二条记录
        org_service.add_member(session, org, "hr_two", role="hr")
        assert len(org_service.list_members(session, org.id)) == 2

        # 不存在的用户
        try:
            org_service.add_member(session, org, "nobody_here")
            raise AssertionError("应当抛出 ValueError")
        except ValueError:
            pass


# ---------- 2. 邀请生命周期 ----------


def test_invite_lifecycle():
    engine = _make_engine()
    with Session(engine) as session:
        hr = _user(session, "hr_inviter")
        org = org_service.get_or_create_org(session, hr)

        invite = org_service.create_invite(session, org, hr, position="后端", difficulty="中级")
        assert org_service.invite_is_active(invite) is True
        assert invite.token

        # 过期即失效
        invite.expires_at = datetime.utcnow() - timedelta(days=1)
        session.add(invite)
        session.commit()
        assert org_service.invite_is_active(invite) is False

        # 吊销即失效
        invite.expires_at = datetime.utcnow() + timedelta(days=1)
        invite.revoked = True
        session.add(invite)
        session.commit()
        assert org_service.invite_is_active(invite) is False


# ---------- 3. 候选人免注册 + 面试归属组织 ----------


def test_candidate_registers_without_account_and_interview_belongs_to_org():
    engine = _make_engine()
    with Session(engine) as session:
        hr = _user(session, "hr_owner")
        org = org_service.get_or_create_org(session, hr)
        invite = org_service.create_invite(session, org, hr, position="后端", difficulty="中级")

        candidate_user = org_service.register_candidate(session, invite, "张三", "z@example.com")
        # 候选人不能登录：无用户名、无密码
        assert candidate_user.role == "candidate"
        assert candidate_user.username is None
        assert candidate_user.password_hash is None

        with patch(
            "server.services.interview_service.generate_first_question",
            _fake_first_question,
        ):
            result = asyncio.run(
                start_interview_session(
                    session,
                    user_id=candidate_user.id,
                    position=invite.position,
                    difficulty=invite.difficulty,
                    duration=invite.duration,
                    style=invite.style,
                    jd_id=invite.jd_id,
                    org_id=invite.org_id,
                )
            )

        interview = result["interview"]
        assert interview.org_id == org.id
        assert interview.user_id == candidate_user.id
        assert result["firstQuestion"]["content"] == "请先做个自我介绍。"
        assert result["stage"]["stage"] == "ask"

        # 排名能查到该候选人
        rows = org_service.candidate_ranking(session, org.id)
        assert len(rows) == 1
        assert rows[0]["name"] == "张三"
        assert rows[0]["interviewId"] == interview.id
        assert rows[0]["position"] == "后端"
        assert rows[0]["totalScore"] is None
        assert rows[0]["status"] == "进行中"


# ---------- 4. 权限矩阵 ----------


def test_permission_matrix_for_reports():
    engine = _make_engine()
    with Session(engine) as session:
        hr = _user(session, "hr_p")
        outsider = _user(session, "outsider")
        admin = _user(session, "root_admin", role="admin")
        org = org_service.get_or_create_org(session, hr)

        viewer = _user(session, "hr_viewer")
        org_service.add_member(session, org, "hr_viewer", role="viewer")

        # 个人练习面试：不属于任何组织
        personal_user = _user(session, "solo_user")
        personal = Interview(user_id=personal_user.id, position="前端", difficulty="初级")
        session.add(personal)
        session.commit()
        session.refresh(personal)

        # 企业候选人面试：归属组织
        cand = org_service.register_candidate(session, org_service.create_invite(
            session, org, hr, position="后端",
        ), "李四")
        corp = Interview(user_id=cand.id, org_id=org.id, position="后端", difficulty="中级")
        session.add(corp)
        session.commit()
        session.refresh(corp)

        # 个人面试：只有本人与 admin 可见
        assert org_service.can_view_interview(session, personal_user, personal) is True
        assert org_service.can_view_interview(session, outsider, personal) is False
        assert org_service.can_view_interview(session, hr, personal) is False
        assert org_service.can_view_interview(session, admin, personal) is True

        # 企业面试：本人（候选人）+ 组织成员 + admin 可见，外部用户不可见
        assert org_service.can_view_interview(session, cand, corp) is True
        assert org_service.can_view_interview(session, hr, corp) is True
        assert org_service.can_view_interview(session, viewer, corp) is True
        assert org_service.can_view_interview(session, outsider, corp) is False
        assert org_service.can_view_interview(session, admin, corp) is True

        # 非法入参不炸
        assert org_service.can_view_interview(session, None, corp) is False
        assert org_service.can_view_interview(session, hr, None) is False

        # 组织管理权：owner/hr 可以，viewer 与外部用户不可以
        assert org_service.can_manage_invite(session, hr, org.id) is True
        assert org_service.can_manage_invite(session, viewer, org.id) is False
        assert org_service.can_manage_invite(session, outsider, org.id) is False


# ---------- 5. 排名排序 ----------


def test_ranking_sorted_by_score_and_grouped_by_invite():
    engine = _make_engine()
    with Session(engine) as session:
        hr = _user(session, "hr_rank")
        org = org_service.get_or_create_org(session, hr)

        invite_a = org_service.create_invite(session, org, hr, position="后端")
        invite_b = org_service.create_invite(session, org, hr, position="前端")

        def make_candidate(name: str, invite, score: float | None) -> None:
            cand = org_service.register_candidate(session, invite, name)
            interview = Interview(
                user_id=cand.id, org_id=org.id, position=invite.position, difficulty="中级",
            )
            session.add(interview)
            session.commit()
            session.refresh(interview)
            if score is not None:
                session.add(Report(interview_id=interview.id, total_score=score, summary=f"{name} 的小结"))
                session.commit()

        make_candidate("低分", invite_a, 61)
        make_candidate("高分", invite_a, 92)
        make_candidate("未完成", invite_a, None)
        make_candidate("前端岗", invite_b, 75)

        rows = org_service.candidate_ranking(session, org.id)
        assert [r["name"] for r in rows] == ["高分", "前端岗", "低分", "未完成"]
        assert rows[0]["totalScore"] == 92

        # 按邀请过滤
        only_a = org_service.candidate_ranking(session, org.id, invite_id=invite_a.id)
        assert [r["name"] for r in only_a] == ["高分", "低分", "未完成"]

        # 邀请列表统计（均值只算已出报告的）
        invites = {i["id"]: i for i in org_service.list_invites(session, org.id)}
        assert invites[invite_a.id]["candidateCount"] == 3
        assert invites[invite_a.id]["scoredCount"] == 2
        assert invites[invite_a.id]["avgScore"] == 76.5
        assert invites[invite_b.id]["avgScore"] == 75.0

        # 组织隔离：换一个组织查不到候选人
        other_hr = _user(session, "hr_other_org")
        other_org: Organization = org_service.get_or_create_org(session, other_hr)
        assert org_service.candidate_ranking(session, other_org.id) == []
        assert len(session.exec(select(Candidate)).all()) == 4


# ---------- 运行入口 ----------

TESTS = [
    test_org_auto_create_and_members,
    test_invite_lifecycle,
    test_candidate_registers_without_account_and_interview_belongs_to_org,
    test_permission_matrix_for_reports,
    test_ranking_sorted_by_score_and_grouped_by_invite,
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
