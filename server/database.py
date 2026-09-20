from sqlmodel import SQLModel, create_engine, Session, select, text
from server.config import settings

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)


def _run_migrations():
    """幂等地为已存在的表补列。"""
    import sqlite3
    is_sqlite = "sqlite" in settings.database_url
    is_postgres = "postgresql" in settings.database_url

    migrations_sqlite = [
        ("interview", "jd_id", "INTEGER"),
        ("interview", "org_id", "INTEGER"),
        ("interview", "stage", "TEXT DEFAULT 'opening'"),
        ("interview", "stage_updated_at", "DATETIME"),
        ("report", "match_score", "REAL"),
        ("report", "match_breakdown", "TEXT"),
        ("user", "username", "TEXT"),
        ("user", "password_hash", "TEXT"),
        ("user", "preferred_avatar_id", "INTEGER"),
        ("user", "preferred_avatar_config_id", "INTEGER"),
        ("knowledgedoc", "is_public", "INTEGER"),
        ("report", "share_token", "TEXT"),
        ("report", "share_expires_at", "DATETIME"),
        ("avatarproviderconfig", "avatar_image", "TEXT DEFAULT ''"),
        ("user", "role", "TEXT DEFAULT 'user'"),
        ("user", "preferred_position", "TEXT DEFAULT ''"),
        ("user", "language", "TEXT DEFAULT 'zh'"),
        ("user", "theme", "TEXT DEFAULT 'light'"),
        ("user", "notification_settings", "TEXT DEFAULT '{}'"),
        # v3.4 企业侧：JD / 知识库组织归属 + 邀请考察重点
        ("jobdescription", "org_id", "INTEGER"),
        ("knowledgedoc", "org_id", "INTEGER"),
        ("candidateinvite", "focus", "TEXT DEFAULT ''"),
        ("interview", "focus", "TEXT DEFAULT ''"),
        # v3.5 具身智能体：默认配置下沉到数据库
        ("avatarproviderconfig", "is_default", "INTEGER DEFAULT 0"),
    ]
    migrations_postgres = [
        ("interview", "stage", "VARCHAR DEFAULT 'opening'"),
        ("interview", "stage_updated_at", "TIMESTAMP"),
        ("interview", "org_id", "INTEGER"),
        ("avatarproviderconfig", "avatar_image", "VARCHAR DEFAULT ''"),
        ("user", "preferred_avatar_config_id", "INTEGER"),
        ("user", "role", "VARCHAR DEFAULT 'user'"),
        ("user", "preferred_position", "VARCHAR DEFAULT ''"),
        ("user", "language", "VARCHAR DEFAULT 'zh'"),
        ("user", "theme", "VARCHAR DEFAULT 'light'"),
        ("user", "notification_settings", "VARCHAR DEFAULT '{}'"),
        # v3.4 企业侧：JD / 知识库组织归属 + 邀请考察重点
        ("jobdescription", "org_id", "INTEGER"),
        ("knowledgedoc", "org_id", "INTEGER"),
        ("candidateinvite", "focus", "VARCHAR DEFAULT ''"),
        ("interview", "focus", "VARCHAR DEFAULT ''"),
        # v3.5 具身智能体：默认配置下沉到数据库
        ("avatarproviderconfig", "is_default", "BOOLEAN DEFAULT FALSE"),
    ]

    if is_sqlite:
        db_path = settings.database_url.replace("sqlite:///", "")
        if not db_path:
            return
        conn = sqlite3.connect(db_path)
        try:
            for table, column, col_type in migrations_sqlite:
                cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
                if column not in cols:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            try:
                conn.execute("UPDATE knowledgedoc SET is_public = 0 WHERE is_public IS NULL")
            except Exception:
                pass
            conn.commit()
        except Exception as e:
            print(f"[migration] skipped: {e}")
        finally:
            conn.close()
    elif is_postgres:
        with engine.connect() as conn:
            for table, column, col_type in migrations_postgres:
                result = conn.execute(
                    text("SELECT COUNT(*) FROM information_schema.columns WHERE table_name = :table AND column_name = :col"),
                    {"table": table, "col": column}
                )
                if result.scalar() == 0:
                    quoted_table = f'"{table}"'
                    conn.execute(text(f"ALTER TABLE {quoted_table} ADD COLUMN {column} {col_type}"))
                    print(f"[migration] added {column} to {table}")
            conn.commit()


def init_db():
    SQLModel.metadata.create_all(engine)
    _run_migrations()
    _seed_avatars()
    _seed_avatar_config_from_env()
    _seed_algorithm_problems()
    _seed_knowledge_versions()
    _seed_user_quotas()


def _seed_avatars():
    """不再预置 Avatar 表数据。具身交互智能体形象由 AvatarProviderConfig 管理。"""
    pass


def _seed_avatar_config_from_env():
    """一次性搬迁：把 .env 中的具身智能体凭证收编为数据库默认配置。

    v3.5 起默认配置一律来自数据库（见 server/services/avatar_config_service.py），
    AVATAR_APP_ID / AVATAR_APP_SECRET / AVATAR_GATEWAY_SERVER / AVATAR_DEFAULT_IMAGE
    已退出运行时解析。这里仅在**首次初始化**时执行一次，避免升级后线上直接掉到
    本地 Lottie 形象；用 data/.avatar_env_seeded 打标，之后即使用户在后台删光了
    所有配置（主动降级 Lottie），重启也不会把 .env 里的旧凭证复活。
    """
    from server.models import AvatarProviderConfig
    from server.services.crypto_service import encrypt

    marker = settings.data_dir / ".avatar_env_seeded"
    if marker.exists():
        return

    app_id = (settings.avatar_app_id or "").strip()
    app_secret = (settings.avatar_app_secret or "").strip()

    with Session(engine) as session:
        if session.exec(select(AvatarProviderConfig)).first():
            pass  # 表里已有配置（走的是后台维护），无需搬迁
        elif app_id and app_secret:
            session.add(AvatarProviderConfig(
                name="默认具身交互智能体",
                app_id=app_id,
                app_secret=encrypt(app_secret),
                gateway_server=(settings.avatar_gateway_server or "").strip()
                or "https://nebula-agent.xingyun3d.com/user/v1/ttsa_v2/session",
                avatar_image=(settings.avatar_default_image or "").strip(),
                is_active=True,
                is_default=True,
            ))
            session.commit()
            print("[migration] 已将 .env 具身智能体凭证搬迁为数据库默认配置")

    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("done", encoding="utf-8")


def get_session():
    with Session(engine) as session:
        yield session


def _seed_algorithm_problems():
    """预置算法题（P3 代码练习模块）。仅首次启动且表为空时写入。"""
    from server.models import AlgorithmProblem
    with Session(engine) as session:
        if session.exec(select(AlgorithmProblem)).first():
            return
        defaults = [
            AlgorithmProblem(
                title="两数之和",
                description="给定一个整数数组 `nums` 和一个整数目标值 `target`，请你在该数组中找出和为目标值的那两个整数，并返回它们的数组下标。\n\n你可以假设每种输入只会对应一个答案。但是，数组中同一个元素在答案里不能重复出现。\n\n**示例：**\n```\n输入：nums = [2,7,11,15], target = 9\n输出：[0,1]\n解释：因为 nums[0] + nums[1] == 9 ，返回 [0, 1] 。\n```",
                difficulty="简单",
                position="通用",
                tags='["数组","哈希表"]',
                examples='[{"input":"nums = [2,7,11,15], target = 9","output":"[0,1]","explanation":"因为 nums[0] + nums[1] == 9"}]',
                test_cases='[{"input":"2 7 11 15\\n9","expected":"0 1"},{"input":"3 2 4\\n6","expected":"1 2"},{"input":"3 3\\n6","expected":"0 1"}]',
            ),
            AlgorithmProblem(
                title="反转链表",
                description="给你单链表的头节点 `head`，请你反转链表，并返回反转后的链表。\n\n**示例：**\n```\n输入：head = [1,2,3,4,5]\n输出：[5,4,3,2,1]\n```",
                difficulty="简单",
                position="通用",
                tags='["链表"]',
                examples='[{"input":"head = [1,2,3,4,5]","output":"[5,4,3,2,1]","explanation":""}]',
                test_cases='[{"input":"1 2 3 4 5","expected":"5 4 3 2 1"},{"input":"1 2","expected":"2 1"},{"input":"","expected":""}]',
            ),
            AlgorithmProblem(
                title="有效括号",
                description="给定一个只包括 `(`、`)`、`{`、`}`、`[`、`]` 的字符串 `s`，判断字符串是否有效。\n\n有效字符串需满足：\n1. 左括号必须用相同类型的右括号闭合。\n2. 左括号必须以正确的顺序闭合。\n3. 每个右括号都有一个对应的相同类型的左括号。\n\n**示例：**\n```\n输入：s = \"()[]{}\"\n输出：true\n```",
                difficulty="简单",
                position="通用",
                tags='["栈","字符串"]',
                examples='[{"input":"s = ()[]{}","output":"true","explanation":""}]',
                test_cases='[{"input":"()","expected":"true"},{"input":"()[]{}","expected":"true"},{"input":"(]","expected":"false"},{"input":"([)]","expected":"false"},{"input":"{[]}","expected":"true"}]',
            ),
            AlgorithmProblem(
                title="最长回文子串",
                description="给你一个字符串 `s`，找到 `s` 中最长的回文子串。\n\n**示例：**\n```\n输入：s = \"babad\"\n输出：\"bab\"\n解释：\"aba\" 同样是符合题意的答案。\n```",
                difficulty="中等",
                position="通用",
                tags='["字符串","动态规划"]',
                examples='[{"input":"s = babad","output":"bab","explanation":"aba 同样是符合题意的答案"}]',
                test_cases='[{"input":"babad","expected":"bab"},{"input":"cbbd","expected":"bb"},{"input":"a","expected":"a"},{"input":"ac","expected":"a"}]',
            ),
        ]
        for p in defaults:
            session.add(p)
        session.commit()


def _seed_knowledge_versions():
    """为现有知识库文档创建初始版本快照（一次性迁移，幂等）。"""
    from server.models import KnowledgeDoc, KnowledgeVersion
    with Session(engine) as session:
        docs = session.exec(select(KnowledgeDoc)).all()
        for doc in docs:
            existing = session.exec(
                select(KnowledgeVersion).where(KnowledgeVersion.doc_id == doc.id)
            ).first()
            if existing:
                continue
            ver = KnowledgeVersion(
                doc_id=doc.id,
                version_number=1,
                content=doc.content,
                title=doc.title,
                position=doc.position,
                difficulty=doc.difficulty,
                tags=doc.tags,
                change_note="初始版本",
                created_by=doc.user_id,
            )
            session.add(ver)
        session.commit()


def _seed_user_quotas():
    """为没有配额记录的用户创建默认配额（幂等）。"""
    from server.models import User, UserQuota
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        for user in users:
            existing = session.exec(
                select(UserQuota).where(UserQuota.user_id == user.id)
            ).first()
            if existing:
                continue
            quota = UserQuota(user_id=user.id)
            session.add(quota)
        session.commit()
