import os
import sys
from pathlib import Path

# 添加 py_deps（沙箱环境下 pip 安装的依赖）
# Docker 环境下跳过，因为依赖已通过 pip 安装且 py_deps 中的二进制文件不兼容
_in_docker = os.path.exists("/.dockerenv")
if not _in_docker:
    _py_deps = Path(__file__).resolve().parent.parent / "py_deps"
    if _py_deps.exists():
        sys.path.insert(0, str(_py_deps))

os.environ["ANONYMIZED_TELEMETRY"] = "False"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from server.database import init_db
from server.routers import knowledge, resume, interview, report, admin, avatar, chat, jd, auth, code, files, recordings, settings

app = FastAPI(title="AI Interviewer API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(settings.router)
app.include_router(knowledge.router)
app.include_router(resume.router)
app.include_router(interview.router)
app.include_router(report.router)
app.include_router(report.share_router)
app.include_router(admin.router)
app.include_router(avatar.router)
app.include_router(chat.router)
app.include_router(jd.router)
app.include_router(code.router)
app.include_router(files.router)
app.include_router(recordings.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
async def root():
    return {"status": "ok", "service": "AI Interviewer API"}
