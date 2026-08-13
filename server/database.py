from sqlmodel import SQLModel, create_engine, Session, text
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
    ]
    conn = sqlite3.connect(db_path)
    try:
        for table, column, col_type in migrations:
            cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if column not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        conn.commit()
    except Exception as e:
        print(f"[migration] skipped: {e}")
    finally:
        conn.close()


def init_db():
    SQLModel.metadata.create_all(engine)
    _run_migrations()


def get_session():
    with Session(engine) as session:
        yield session
