import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    avatar_app_id: str = ""
    avatar_app_secret: str = ""
    avatar_gateway_server: str = "https://test-nebula-agent.xmov.ai/user/v1/ttsa_v2/session"

    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"

    embedding_api_key: str = ""
    embedding_base_url: str = "https://api.siliconflow.cn/v1"
    embedding_model: str = "BAAI/bge-m3"

    admin_password: str = "admin123"

    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'app.db'}"

    data_dir: Path = BASE_DIR / "data"
    chroma_dir: Path = BASE_DIR / "chroma_db"

    encryption_key: str = "change-me-in-production-32bytes!!"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
    )


settings = settings = Settings()

DATA_DIR = settings.data_dir
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "resumes").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "knowledge").mkdir(parents=True, exist_ok=True)
settings.chroma_dir.mkdir(parents=True, exist_ok=True)
