from sqlmodel import SQLModel, create_engine, Session, select, text
from server.config import settings

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)


def _run_migrations():
    """幂等地为已存在的表补列（SQLite ALTER TABLE ADD COLUMN，列已存在时忽略报错）。"""
    import sqlite3
    if "sqlite" not in settings.database_url:
        return
    db_path = settings.database_url.replace("sqlite:///", "")
    if not db_path:
        return
    migrations = [
        ("interview", "jd_id", "INTEGER"),
        ("report", "match_score", "REAL"),
        ("report", "match_breakdown", "TEXT"),
        # P2 用户体系：为已存在的 user 表补 username/password_hash/preferred_avatar_id
        ("user", "username", "TEXT"),
        ("user", "password_hash", "TEXT"),
        ("user", "preferred_avatar_id", "INTEGER"),
        # P2 知识文档：补 is_public（混合 public/private）
        ("knowledgedoc", "is_public", "INTEGER"),
        ("report", "share_token", "TEXT"),
        ("report", "share_expires_at", "DATETIME"),
    ]
    conn = sqlite3.connect(db_path)
    try:
        for table, column, col_type in migrations:
            cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if column not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        # 兼容旧数据：knowledgedoc.is_public 新列默认 NULL，更新为 0（private）
        try:
            conn.execute("UPDATE knowledgedoc SET is_public = 0 WHERE is_public IS NULL")
        except Exception:
            pass
        conn.commit()
    except Exception as e:
        print(f"[migration] skipped: {e}")
    finally:
        conn.close()


def init_db():
    SQLModel.metadata.create_all(engine)
    _run_migrations()
    _seed_avatars()
    _seed_algorithm_problems()


def _seed_avatars():
    """预置占位数字人形象（2D，资源后补）。仅首次启动且表为空时写入。"""
    from server.models import Avatar
    with Session(engine) as session:
        if session.exec(select(Avatar)).first():
            return
        defaults = [
            Avatar(name="默认面试官", cover_url="", extra='{"emoji":"😊","color":"primary"}'),
            Avatar(name="专业面试官", cover_url="", extra='{"emoji":"🧑‍💼","color":"blue"}'),
        ]
        for a in defaults:
            session.add(a)
        session.commit()


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
