import os
import sys
import json
import uuid
from datetime import datetime as dt
from pathlib import Path
from typing import Optional

# 添加 py_deps（沙箱环境下 pip 安装的依赖）
# Docker 环境下跳过，因为依赖已通过 pip 安装且 py_deps 中的二进制文件不兼容
_in_docker = os.path.exists("/.dockerenv")
if not _in_docker:
    _py_deps = Path(__file__).resolve().parent.parent / "py_deps"
    if _py_deps.exists():
        sys.path.insert(0, str(_py_deps))

os.environ["ANONYMIZED_TELEMETRY"] = "False"

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from server.database import engine, init_db
from server.routers import knowledge, resume, interview, report, admin, avatar, chat, jd, auth, code, files, recordings, settings, metrics, profile
from server.services.avatar_brain_service import (
    resolve_session,
    generate_stream,
    generate_non_stream,
    _extract_last_user_message,
)
from server.services.interview_brain_service import (
    resolve_interview_session,
    generate_interview_stream,
    generate_interview_non_stream,
)

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
app.include_router(metrics.router)
app.include_router(profile.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.on_event("shutdown")
async def on_shutdown():
    """回收 MCP 子进程，避免热重载残留。"""
    try:
        from server.services.mcp_service import shutdown_all

        await shutdown_all()
    except Exception as e:
        print(f"[MCP] shutdown failed: {e}")


@app.post("/v1/chat/completions")
async def root_v1_chat_completions(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_base: Optional[str] = Header(None),
):
    """根级 /v1/chat/completions — 供 E2EMPServer BrainClient (localhost:8000) 调用.

    三种模式：
    1. 面试代理模式：Bearer token 为 interview avatar session token → 面试官大脑
    2. 聊天代理模式：Bearer token 为 avatar session token → RAG+LLM（学习导师）
    3. 直连模式：Bearer token 为 LLM API key + X-Api-Base → 直接转发 LLM
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    token_str = authorization.split(" ", 1)[1]

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")

    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(400, "Missing messages")

    is_stream = body.get("stream", True)
    user_message = _extract_last_user_message(messages)

    # 尝试作为面试 token 解析（优先），再尝试聊天 token
    with Session(engine) as db:
        interview_resolved = resolve_interview_session(db, token_str)
        resolved = None if interview_resolved is not None else resolve_session(db, token_str)

    if interview_resolved is not None:
        # ── 面试代理模式：面试官大脑 ──
        user, interview = interview_resolved
        print(f"[Root V1] Interview proxy mode, interview_id={interview.id}, user={user.id}")

        if not user_message:
            raise HTTPException(400, "No user message found in messages")

        sse_headers = {
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
        if is_stream:
            return StreamingResponse(
                generate_interview_stream(user_message, interview.id),
                media_type="text/event-stream",
                headers=sse_headers,
            )
        return await generate_interview_non_stream(user_message, interview.id)

    if resolved is not None:
        # ── Avatar 代理模式：RAG+LLM ──
        user, conv = resolved
        print(f"[Root V1] Avatar proxy mode, conv_id={conv.id}, user_msg={user_message}")

        if not user_message:
            raise HTTPException(400, "No user message found in messages")

        if is_stream:
            return StreamingResponse(
                generate_stream(db, conv.id, user_message),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            return await generate_non_stream(db, conv.id, user_message)
    else:
        # ── 直连模式：代理到真实 LLM ──
        if not x_api_base:
            raise HTTPException(400, "X-Api-Base header required for direct LLM mode")
        print(f"[Root V1] Direct LLM mode, base={x_api_base}")

        from openai import AsyncOpenAI
        client = AsyncOpenAI(base_url=x_api_base, api_key=token_str)

        model = body.get("model", "gpt-3.5-turbo")
        extra_body = body.get("extra_body", {})

        if is_stream:
            async def direct_stream():
                chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
                created_ts = int(dt.utcnow().timestamp())
                try:
                    async for chunk in await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        stream=True,
                        **extra_body,
                    ):
                        delta = chunk.choices[0].delta.content or ""
                        if delta:
                            sse_chunk = json.dumps(
                                {
                                    "id": chunk_id,
                                    "object": "chat.completion.chunk",
                                    "created": created_ts,
                                    "model": model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {"content": delta},
                                            "finish_reason": None,
                                        }
                                    ],
                                },
                                ensure_ascii=False,
                            )
                            yield f"data: {sse_chunk}\n\n"
                except Exception as e:
                    print(f"[Root V1] Direct stream error: {e}")

                final_chunk = json.dumps(
                    {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "created": created_ts,
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {},
                                "finish_reason": "stop",
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
                yield f"data: {final_chunk}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                direct_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=False,
                **extra_body,
            )
            return response.model_dump()


@app.get("/")
async def root():
    return {"status": "ok", "service": "AI Interviewer API"}


@app.get("/api/mode")
async def runtime_mode():
    """当前运行模式，供前端展示提示条。

    - cloud：已配置云端 LLM 凭证
    - local-llm：LLM 指向本地 Ollama（无需云端凭证）
    - offline：离线规则模式（无模型，题库 + 规则驱动）
    - unconfigured：未配置 LLM
    """
    from server.config import settings as app_settings

    url = (app_settings.llm_base_url or "").lower()
    if app_settings.offline_mode:
        mode = "offline"
    elif "ollama" in url or "11434" in url:
        mode = "local-llm"
    elif app_settings.llm_api_key and not app_settings.llm_api_key.startswith("<"):
        mode = "cloud"
    else:
        mode = "unconfigured"

    return {
        "mode": mode,
        "llmModel": app_settings.llm_model,
        "embeddingProvider": app_settings.embedding_provider,
        "avatarConfigured": bool(app_settings.avatar_app_id and app_settings.avatar_app_secret),
    }
