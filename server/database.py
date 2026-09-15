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
    ]
    migrations_postgres = [
        ("avatarproviderconfig", "avatar_image", "VARCHAR DEFAULT ''"),
        ("user", "preferred_avatar_config_id", "INTEGER"),
        ("user", "role", "VARCHAR DEFAULT 'user'"),
        ("user", "preferred_position", "VARCHAR DEFAULT ''"),
        ("user", "language", "VARCHAR DEFAULT 'zh'"),
        ("user", "theme", "VARCHAR DEFAULT 'light'"),
        ("user", "notification_settings", "VARCHAR DEFAULT '{}'"),
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
    _seed_algorithm_problems()
    _seed_knowledge_versions()
    _seed_user_quotas()


def _seed_avatars():
    """不再预置 Avatar 表数据。具身交互智能体形象由 AvatarProviderConfig 管理。"""
    pass


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
            import json as _json
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
