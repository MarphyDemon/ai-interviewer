import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent
# 项目根目录（server/ 的上一级）
PROJECT_ROOT = BASE_DIR.parent


class Settings(BaseSettings):
    avatar_app_id: str = ""
    avatar_app_secret: str = ""
    avatar_gateway_server: str = "https://test-nebula-agent.xmov.ai/user/v1/ttsa_v2/session"
    avatar_default_image: str = "https://public-xmov.oss-cn-hangzhou.aliyuncs.com/avatar_sdk_material/M_CN03_show03__1080x1920__FS001__3DS16__T4__caixiangyu_15339_new.png"
    avatar_proxy_base_url: str = ""

    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"

    embedding_api_key: str = ""
    embedding_base_url: str = "https://api.siliconflow.cn/v1"
    embedding_model: str = "BAAI/bge-m3"

    admin_password: str = "admin123"

    # 数据库：默认 SQLite，设置 DATABASE_URL 环境变量可切换 PostgreSQL
    # e.g. postgresql://user:password@localhost:5432/ai_interviewer
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'app.db'}"

    # S3 兼容对象存储（可选，不设置则使用本地文件存储）
    s3_endpoint: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "ai-interviewer"
    s3_region: str = "auto"

    # 录制文件存储目录（本地模式）
    recordings_dir: Path = PROJECT_ROOT / "data" / "recordings"

    data_dir: Path = PROJECT_ROOT / "data"
    chroma_dir: Path = PROJECT_ROOT / "data" / "chroma_db"

    encryption_key: str = "change-me-in-production-32bytes!!"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
    )


settings = Settings()

DATA_DIR = settings.data_dir
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "resumes").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "knowledge").mkdir(parents=True, exist_ok=True)
settings.recordings_dir.mkdir(parents=True, exist_ok=True)
settings.chroma_dir.mkdir(parents=True, exist_ok=True)
