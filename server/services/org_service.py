"""企业侧（候选人初筛）服务：组织、成员、候选人邀请与排名。

核心设计：候选人 = role="candidate" 的无密码 User。
企业侧不引入第二套账号体系，面试/报告/录音/指标全部复用个人练习的链路，
本模块只负责「组织归属」与「邀请生命周期」这两件事。

权限模型（最小闭环）：
- 本人（user_id 相同）→ 读写自己的面试
- 组织成员（owner/hr/viewer）→ 只读本组织的候选人面试与报告
- admin → 只读全部（沿用原有超管语义）
"""
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Session, or_, select

from server.models import (
    Candidate,
    CandidateInvite,
    Interview,
    JobDescription,
    KnowledgeDoc,
    Organization,
    OrgMember,
    Report,
    User,
)

# 可管理组织（发邀请、加成员）的角色
ORG_MANAGER_ROLES = ("owner", "hr")
# 可查看本组织候选人报告的角色
ORG_VIEWER_ROLES = ("owner", "hr", "viewer")

# 候选人邀请默认有效期
INVITE_DEFAULT_DAYS = 30


def _gen_token(length: int = 12) -> str:
    """base62 短码，用于候选人邀请链接。"""
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ---------- 组织与成员 ----------

def get_org_for_user(session: Session, user_id: int) -> Optional[Organization]:
    """返回用户所属的组织（一个用户当前只归属一个组织）。"""
    member = session.exec(
        select(OrgMember).where(OrgMember.user_id == user_id)
    ).first()
    if not member:
        return None
    return session.get(Organization, member.org_id)


def get_or_create_org(session: Session, user: User) -> Organization:
    """获取用户的组织，没有则创建并成为 owner（自助开通，无需审批）。"""
    org = get_org_for_user(session, user.id)
    if org:
        return org

    name = (user.username or "我的").strip()
    org = Organization(name=f"{name} 的团队", owner_id=user.id)
    session.add(org)
    session.commit()
    session.refresh(org)

    session.add(OrgMember(org_id=org.id, user_id=user.id, role="owner"))
    session.commit()
    return org


def member_role(session: Session, org_id: int, user_id: int) -> Optional[str]:
    member = session.exec(
        select(OrgMember).where(
            OrgMember.org_id == org_id,
            OrgMember.user_id == user_id,
        )
    ).first()
    return member.role if member else None


def list_members(session: Session, org_id: int) -> list[dict]:
    members = session.exec(select(OrgMember).where(OrgMember.org_id == org_id)).all()
    rows = []
    for m in members:
        user = session.get(User, m.user_id)
        rows.append({
            "userId": m.user_id,
            "username": (user.username if user else None) or "（未知）",
            "role": m.role,
            "createdAt": m.created_at.isoformat() if m.created_at else None,
        })
    return rows


def add_member(session: Session, org: Organization, username: str, role: str = "hr") -> OrgMember:
    """按用户名把已有用户加入组织。已存在则返回原记录。"""
    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        raise ValueError("用户不存在")
    if role not in ORG_MANAGER_ROLES + ("viewer",):
        raise ValueError("无效的角色")

    existing = session.exec(
        select(OrgMember).where(OrgMember.org_id == org.id, OrgMember.user_id == user.id)
    ).first()
    if existing:
        return existing

    member = OrgMember(org_id=org.id, user_id=user.id, role=role)
    session.add(member)
    session.commit()
    session.refresh(member)
    return member


# ---------- 权限判定 ----------

def can_view_interview(session: Session, user: Optional[User], interview: Optional[Interview]) -> bool:
    """能否查看该场面试（含报告、对话、PDF）。"""
    if not user or not interview:
        return False
    if interview.user_id == user.id:
        return True
    if user.role == "admin":
        return True
    if not interview.org_id:
        return False
    return member_role(session, interview.org_id, user.id) in ORG_VIEWER_ROLES


def can_manage_invite(session: Session, user: Optional[User], org_id: int) -> bool:
    if not user:
        return False
    return member_role(session, org_id, user.id) in ORG_MANAGER_ROLES


# ---------- 组织共享资源（JD / 知识库文档）的可见与可写判定 ----------

def user_org_id(session: Session, user_id: Optional[int]) -> Optional[int]:
    """用户所属组织 id（当前模型下一个用户只归属一个组织）。"""
    if not user_id:
        return None
    member = session.exec(
        select(OrgMember).where(OrgMember.user_id == user_id)
    ).first()
    return member.org_id if member else None


def can_view_org_resource(
    session: Session,
    user: Optional[User],
    owner_id: Optional[int],
    org_id: Optional[int],
) -> bool:
    """组织共享资源可见性：本人、超管、同组织成员（owner/hr/viewer）。"""
    if not user:
        return False
    if owner_id is not None and owner_id == user.id:
        return True
    if user.role == "admin":
        return True
    if not org_id:
        return False
    return member_role(session, org_id, user.id) in ORG_VIEWER_ROLES


def can_manage_org_resource(
    session: Session,
    user: Optional[User],
    owner_id: Optional[int],
    org_id: Optional[int],
) -> bool:
    """组织共享资源可写性：本人、超管、组织管理角色（owner/hr）。"""
    if not user:
        return False
    if owner_id is not None and owner_id == user.id:
        return True
    if user.role == "admin":
        return True
    if not org_id:
        return False
    return member_role(session, org_id, user.id) in ORG_MANAGER_ROLES


def visible_knowledge_doc_ids(
    session: Session,
    user_id: Optional[int],
    org_id: Optional[int],
) -> set[int]:
    """面试 RAG 可用的知识文档：全局公开 ∪ 本人私有 ∪ 所在组织知识库。

    向量库（ChromaDB）的 chunk 上没有归属元数据，因此以数据库为权威，
    检索出候选片段后再按本函数给出的 doc_id 集合过滤，避免私有文档跨用户串检。
    """
    conditions = [KnowledgeDoc.is_public == True]  # noqa: E712
    if user_id:
        conditions.append(KnowledgeDoc.user_id == user_id)
    if org_id:
        conditions.append(KnowledgeDoc.org_id == org_id)
    rows = session.exec(select(KnowledgeDoc.id).where(or_(*conditions))).all()
    return {int(r) for r in rows if r is not None}


def visible_jd_ids(
    session: Session,
    user_id: Optional[int],
    org_id: Optional[int],
) -> set[int]:
    """可选的岗位 JD：本人创建的 ∪ 所在组织共享的。"""
    conditions = []
    if user_id:
        conditions.append(JobDescription.user_id == user_id)
    if org_id:
        conditions.append(JobDescription.org_id == org_id)
    if not conditions:
        return set()
    rows = session.exec(select(JobDescription.id).where(or_(*conditions))).all()
    return {int(r) for r in rows if r is not None}


def filter_visible_chunks(results: list[dict], allowed: set[int]) -> list[dict]:
    """按文档归属过滤向量检索结果（chunk metadata 里只有 doc_id）。"""
    filtered = []
    for r in results:
        try:
            doc_id = int((r.get("metadata") or {}).get("doc_id"))
        except (TypeError, ValueError):
            continue
        if doc_id in allowed:
            filtered.append(r)
    return filtered


# ---------- 候选人邀请 ----------

def invite_is_active(invite: CandidateInvite) -> bool:
    if invite.revoked:
        return False
    if invite.expires_at and invite.expires_at < datetime.utcnow():
        return False
    return True


def create_invite(
    session: Session,
    org: Organization,
    user: User,
    position: str,
    jd_id: Optional[int] = None,
    difficulty: str = "mid",
    duration: int = 30,
    style: str = "friendly",
    note: str = "",
    focus: str = "",
    expires_in_days: int = INVITE_DEFAULT_DAYS,
) -> CandidateInvite:
    invite = CandidateInvite(
        org_id=org.id,
        token=_gen_token(),
        position=position,
        jd_id=jd_id,
        difficulty=difficulty,
        duration=duration,
        style=style,
        note=note,
        # 考察重点由 HR 自定义，候选人开始面试时注入 prompt
        focus=focus.strip()[:2000],
        created_by=user.id,
        expires_at=datetime.utcnow() + timedelta(days=expires_in_days),
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return invite


def register_candidate(session: Session, invite: CandidateInvite, name: str, email: str = "") -> User:
    """为候选人创建无密码 User（免注册），并登记到该邀请下。

    username 留空、password_hash 留空：候选人无法通过 /api/auth/login 登录，
    只能凭邀请链接换取 token，因此不会污染用户名空间。
    """
    candidate_user = User(
        anonymous_uuid=uuid.uuid4().hex,
        username=None,
        password_hash=None,
        role="candidate",
    )
    session.add(candidate_user)
    session.commit()
    session.refresh(candidate_user)

    session.add(Candidate(
        invite_id=invite.id,
        org_id=invite.org_id,
        user_id=candidate_user.id,
        name=name.strip()[:64],
        email=email.strip()[:128],
    ))
    session.commit()
    return candidate_user


def candidate_ranking(
    session: Session,
    org_id: int,
    invite_id: Optional[int] = None,
    limit: int = 100,
) -> list[dict]:
    """候选人成绩列表：按报告总分倒序（未出报告的排最后）。"""
    stmt = select(Candidate).where(Candidate.org_id == org_id)
    if invite_id:
        stmt = stmt.where(Candidate.invite_id == invite_id)
    candidates = session.exec(stmt.order_by(Candidate.created_at.desc()).limit(limit)).all()

    rows: list[dict] = []
    for c in candidates:
        interview = session.exec(
            select(Interview)
            .where(Interview.user_id == c.user_id)
            .order_by(Interview.started_at.desc())
        ).first()
        report = None
        if interview:
            report = session.exec(
                select(Report).where(Report.interview_id == interview.id)
            ).first()
        invite = session.get(CandidateInvite, c.invite_id)
        rows.append({
            "candidateId": c.id,
            "name": c.name or "未填写",
            "email": c.email,
            "inviteId": c.invite_id,
            "position": invite.position if invite else "",
            "interviewId": interview.id if interview else None,
            "status": interview.status if interview else "未开始",
            "stage": interview.stage if interview else None,
            "totalScore": report.total_score if report else None,
            "summary": (report.summary or "")[:200] if report else "",
            "startedAt": interview.started_at.isoformat() if interview and interview.started_at else None,
            "endedAt": interview.ended_at.isoformat() if interview and interview.ended_at else None,
            "createdAt": c.created_at.isoformat() if c.created_at else None,
        })

    rows.sort(key=lambda r: (r["totalScore"] is None, -(r["totalScore"] or 0)))
    return rows


def list_invites(session: Session, org_id: int) -> list[dict]:
    """邀请列表，附带候选人进度统计。"""
    invites = session.exec(
        select(CandidateInvite)
        .where(CandidateInvite.org_id == org_id)
        .order_by(CandidateInvite.created_at.desc())
    ).all()

    rows = []
    for inv in invites:
        cands = session.exec(
            select(Candidate).where(Candidate.invite_id == inv.id)
        ).all()
        scores = [
            r["totalScore"]
            for r in (candidate_ranking(session, org_id, invite_id=inv.id) or [])
            if r["totalScore"] is not None
        ]
        rows.append({
            "id": inv.id,
            "token": inv.token,
            "position": inv.position,
            "jdId": inv.jd_id,
            "difficulty": inv.difficulty,
            "duration": inv.duration,
            "style": inv.style,
            "note": inv.note,
            "focus": inv.focus,
            "candidateCount": len(cands),
            "scoredCount": len(scores),
            "avgScore": round(sum(scores) / len(scores), 1) if scores else None,
            "active": invite_is_active(inv),
            "expiresAt": inv.expires_at.isoformat() if inv.expires_at else None,
            "createdAt": inv.created_at.isoformat() if inv.created_at else None,
        })
    return rows
