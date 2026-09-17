"""数据迁移脚本：SQLite → PostgreSQL

用法：
  python -m server.scripts.migrate_to_pg
  
环境变量：
  DATABASE_URL=postgresql://user:password@localhost:5432/ai_interviewer

说明：
  读取当前 SQLite 数据库中的所有数据，写入 PostgreSQL 目标数据库。
  PostgreSQL 需先由 SQLModel 创建好表结构（运行一次 init_db 即可）。
  迁移完成后，将 DATABASE_URL 写入 .env 即可切换。
"""
import os
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 添加 py_deps（沙箱环境下 pip 安装的依赖）
py_deps = PROJECT_ROOT / "py_deps"
if py_deps.exists():
    sys.path.insert(0, str(py_deps))

# 先 CGI 层禁用 SSL_CERT_FILE（项目已知问题）
os.environ.pop("SSL_CERT_FILE", None)

from sqlmodel import Session, create_engine, SQLModel
from server.config import settings
from server.models import *  # noqa: F401, F403 — 注册所有模型


def get_sqlite_tables(engine) -> dict[str, list[dict]]:
    """从 SQLite 读取所有表数据。"""
    from sqlalchemy import MetaData

    metadata = MetaData()
    metadata.reflect(bind=engine)
    data = {}
    with Session(engine) as session:
        for table_name, table in metadata.tables.items():
            rows = session.execute(table.select()).fetchall()
            columns = [c.name for c in table.columns]
            data[table_name] = [dict(zip(columns, row, strict=False)) for row in rows]
            print(f"  [{table_name}] {len(rows)} 行")
    return data


def migrate():
    pg_url = os.environ.get("DATABASE_URL") or settings.database_url
    if not pg_url or "postgresql" not in pg_url:
        print("❌ 请设置 DATABASE_URL 环境变量为 PostgreSQL 连接串")
        print("   例如: DATABASE_URL=postgresql://user:password@localhost:5432/ai_interviewer")
        sys.exit(1)

    # SQLite 路径：从硬编码路径或环境变量中的 sqlite URL 读取
    sqlite_env = os.environ.get("SQLITE_URL", "")
    if sqlite_env:
        sqlite_path = sqlite_env.replace("sqlite:///", "")
    else:
        # 默认路径
        sqlite_path = str(PROJECT_ROOT / "data" / "app.db")
    if not os.path.exists(sqlite_path):
        print(f"❌ SQLite 数据库不存在: {sqlite_path}")
        sys.exit(1)

    sqlite_url = f"sqlite:///{sqlite_path}"
    sqlite_engine = create_engine(sqlite_url, echo=False)

    print(f"📖 读取 SQLite: {sqlite_path}")
    table_data = get_sqlite_tables(sqlite_engine)

    total_rows = sum(len(rows) for rows in table_data.values())
    if total_rows == 0:
        print("⚠️  SQLite 数据库为空，无数据可迁移")
        return

    print(f"\n📝 写入 PostgreSQL: {pg_url}")
    pg_engine = create_engine(pg_url, echo=False)

    # 确保表结构存在
    SQLModel.metadata.create_all(pg_engine)

    with Session(pg_engine) as session:
        for table_name, rows in table_data.items():
            if not rows:
                continue
            # 获取目标表对象
            table = SQLModel.metadata.tables.get(table_name)
            if table is None:
                print(f"  ⚠️ 跳过未知表: {table_name}")
                continue
            try:
                session.execute(table.insert(), rows)
                session.commit()
                print(f"  ✅ [{table_name}] 写入 {len(rows)} 行")
            except Exception as e:
                session.rollback()
                print(f"  ❌ [{table_name}] 写入失败: {e}")

    print(f"\n✅ 迁移完成！共迁移 {total_rows} 行数据到 {len(table_data)} 个表")
    print("\n下一步：将以下配置添加到 server/.env：")
    print(f"  DATABASE_URL={pg_url}")


if __name__ == "__main__":
    migrate()