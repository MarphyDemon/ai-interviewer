"""面试官 Brain 服务：把数字人 SDK 的 LLM 请求代理为「面试官大脑」。

与 avatar_brain_service（聊天/学习导师）并列，二者通过 token 归属分流：
- AvatarSessionToken        → 聊天链路（RAG + 学习导师 prompt）
- InterviewAvatarSession    → 面试链路（本模块：面试官 prompt + 题库 RAG + 面试记录）

核心流程：
1. 校验面试 token → 定位面试记录（Interview）
2. 取 SDK 传来的最新 user 消息（ASR 识别结果）
3. RAG 检索该岗位/难度的题库素材
4. 组织「面试官」system prompt + 面试历史
5. 流式调用 LLM，以标准 OpenAI SSE 返回给 SDK（SDK 负责 TTS/口型/表情）
6. 落库 user / assistant 消息到 InterviewMessage，保证多轮记忆与报告一致
"""
import json
import secrets
from datetime import datetime, timedelta
from typing import AsyncGenerator, Optional

from sqlmodel import Session, select

from server.models import Interview, InterviewAvatarSession, InterviewMessage, User


TOKEN_TTL_HOURS = 24


# ---------- Token 管理 ----------

def create_interview_session(
    session: Session,
    user_id: int,
    interview_id: int,
) -> str:
    """为某场面试签发数字人会话 token。返回 token 字符串。

    同一场面试可签发多个 token（例如刷新页面后），旧 token 保留至过期。
    """
    interview = session.get(Interview, interview_id)
    if not interview or interview.user_id != user_id:
        raise ValueError(f"Interview {interview_id} not found or not owned by user")

    token_str = secrets.token_hex(32)
    expires_at = datetime.utcnow() + timedelta(hours=TOKEN_TTL_HOURS)

    session.add(
        InterviewAvatarSession(
            user_id=user_id,
            interview_id=interview_id,
            token=token_str,
            expires_at=expires_at,
        )
    )
    session.commit()
    return token_str


def resolve_interview_session(
    session: Session, token_str: str
) -> Optional[tuple[User, Interview]]:
    """通过面试 token 查找用户与面试记录。token 无效/过期返回 None。"""
    token_obj = session.exec(
        select(InterviewAvatarSession).where(
            InterviewAvatarSession.token == token_str
        )
    ).first()
    if not token_obj:
        return None

    if datetime.utcnow() > token_obj.expires_at:
        return None

    user = session.get(User, token_obj.user_id)
    interview = session.get(Interview, token_obj.interview_id)
    if not user or not interview:
        return None

    return user, interview


# ---------- Prompt 构建 ----------

_STYLE_DESC = {
    "strict": "严格犀利，会直接指出回答中的漏洞",
    "friendly": "温和友好，以引导和鼓励为主",
    "pressure": "高压追问，会连续深挖细节考察抗压能力",
}


def build_interviewer_prompt(
    session: Session,
    interview: Interview,
    knowledge: str = "",
    resume_text: str = "",
    jd_text: str = "",
    remaining_seconds: Optional[int] = None,
) -> str:
    """构建面试官 system prompt（口播友好版）。

    与 interview_service._build_system_prompt 的区别：这里输出的是**直接口播的自然语言**，
    不走 JSON 状态机，因此强制约束「无 Markdown / 无 emoji / 长度可控」。
    """
    style = _STYLE_DESC.get(interview.style, interview.style or "温和友好")

    prompt = f"""你正在以面试官的身份，与候选人进行一场 {interview.position} 方向、{interview.difficulty} 级别的模拟面试。
你的面试风格是：{style}。

## 你的职责
1. 每次只问一个问题，等候选人回答后再决定下一步
2. 根据回答质量决定是否追问（同一题最多追问 2 次），追问要针对细节、考察真实理解
3. 回答含糊时先追问；明显跑题时简短拉回；完全答不上来时换一个角度或降低难度
4. 面试中段可安排 1~2 道算法/编码题，出题后说明题意并等待候选人作答

## 表达要求（极其重要，你的话会被直接朗读出来）
- 只输出你要说的话本身，不要输出任何格式标记
- 禁止 Markdown（如 **加粗**、# 标题、- 列表）、禁止 emoji
- 禁止输出括号内的动作描述或旁白（如"（微笑）"）
- 单次回复控制在 120 字以内，除非在讲解参考答案
- 语言与候选人保持一致，中文面试用中文
"""
    if jd_text:
        prompt += f"\n## 目标岗位 JD（据此针对性提问与追问）\n{jd_text}\n"
    if resume_text:
        prompt += f"\n## 候选人简历（可针对性提问项目经历）\n{resume_text}\n"
    if knowledge:
        prompt += f"\n## 参考知识素材（可据此出题与判断回答质量）\n{knowledge}\n"
    if remaining_seconds is not None:
        if remaining_seconds <= 0:
            prompt += "\n## 时间提示\n面试时间已到，请用一两句话礼貌收尾，告知候选人面试结束。\n"
        elif remaining_seconds <= 180:
            prompt += (
                f"\n## 时间提示\n仅剩约 {remaining_seconds // 60} 分钟，"
                "请开始收束话题，不要再开启新的大题。\n"
            )
    return prompt


# ---------- 上下文加载 ----------

async def _retrieve_knowledge(session: Session, position: str, difficulty: str) -> str:
    """复用面试编排的 RAG 检索（按 position 过滤，无结果则全库）。"""
    from server.services.interview_service import _retrieve_knowledge as _rk

    return await _rk(session, position, difficulty)


def _load_messages(session: Session, interview: Interview) -> list[dict]:
    """加载面试历史为 LLM messages 格式（interviewer → assistant）。"""
    rows = session.exec(
        select(InterviewMessage)
        .where(InterviewMessage.interview_id == interview.id)
        .order_by(InterviewMessage.created_at)
    ).all()
    return [
        {
            "role": "assistant" if m.role == "interviewer" else "user",
            "content": m.content,
        }
        for m in rows
    ]


def _remaining_seconds(interview: Interview) -> int:
    if not interview.started_at:
        return interview.duration * 60
    elapsed = (datetime.utcnow() - interview.started_at).total_seconds()
    return int(interview.duration * 60 - elapsed)


def _build_context(session: Session, interview: Interview, knowledge: str) -> list[dict]:
    """构建 system + 历史的 messages（不含本次 user 消息，由调用方追加）。"""
    resume_text = ""
    if interview.resume_id:
        from server.models import Resume

        resume = session.get(Resume, interview.resume_id)
        if resume:
            resume_text = (resume.parsed_text or "")[:2000]

    jd_text = ""
    if interview.jd_id:
        from server.models import JobDescription

        jd = session.get(JobDescription, interview.jd_id)
        if jd:
            jd_text = (jd.content or "")[:3000]

    system_prompt = build_interviewer_prompt(
        session=session,
        interview=interview,
        knowledge=knowledge,
        resume_text=resume_text,
        jd_text=jd_text,
        remaining_seconds=_remaining_seconds(interview),
    )
    return [{"role": "system", "content": system_prompt}] + _load_messages(session, interview)


# ---------- 流式生成 ----------

def _sse_chunk(chunk_id: str, created_ts: int, model: str, delta: dict, finish: Optional[str] = None) -> str:
    """构造标准 OpenAI SSE chunk。"""
    payload = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": created_ts,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def generate_interview_stream(
    user_message: str,
    interview_id: int,
) -> AsyncGenerator[str, None]:
    """面试官流式生成：RAG → LLM → 标准 OpenAI SSE。

    使用独立 session 操作数据库，避免依赖注入的 session 在异步流期间被关闭。
    """
    import uuid
    from datetime import datetime as dt

    from openai import AsyncOpenAI

    from server.database import engine
    from server.services.common import get_active_llm_config
    from server.services.interview_service import save_message

    with Session(engine) as db:
        interview = db.get(Interview, interview_id)
        if not interview:
            print(f"[Interview Brain] Interview {interview_id} not found")
            yield _sse_chunk(
                f"chatcmpl-{uuid.uuid4().hex}",
                int(dt.utcnow().timestamp()),
                "",
                {"content": ""},
                "stop",
            )
            yield "data: [DONE]\n\n"
            return

        # 落库候选人回答（_build_context 会一并读出，无需再单独追加）
        save_message(db, interview_id, "user", user_message)

        knowledge = await _retrieve_knowledge(db, interview.position, interview.difficulty)
        messages = _build_context(db, interview, knowledge)
        cfg = get_active_llm_config(db)

    client = AsyncOpenAI(base_url=cfg.base_url, api_key=cfg.api_key)

    full_response = ""
    chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
    created_ts = int(dt.utcnow().timestamp())

    try:
        async for chunk in await client.chat.completions.create(
            model=cfg.model, messages=messages, stream=True
        ):
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full_response += delta
                yield _sse_chunk(chunk_id, created_ts, cfg.model, {"content": delta})
    except Exception as e:
        print(f"[Interview Brain] Stream error: {e}")
    finally:
        yield _sse_chunk(chunk_id, created_ts, cfg.model, {}, "stop")
        yield "data: [DONE]\n\n"

        # 落库面试官回复（供多轮记忆与报告生成使用）
        if full_response:
            try:
                with Session(engine) as db:
                    save_message(db, interview_id, "interviewer", full_response)
            except Exception as e:
                print(f"[Interview Brain] Failed to save interviewer message: {e}")


async def generate_interview_non_stream(
    user_message: str,
    interview_id: int,
) -> dict:
    """面试官非流式生成（SDK 请求 stream=false 时使用）。"""
    from openai import AsyncOpenAI

    from server.database import engine
    from server.services.common import get_active_llm_config
    from server.services.interview_service import save_message

    with Session(engine) as db:
        interview = db.get(Interview, interview_id)
        if not interview:
            raise ValueError(f"Interview {interview_id} not found")

        # 落库候选人回答（_build_context 会一并读出，无需再单独追加）
        save_message(db, interview_id, "user", user_message)

        knowledge = await _retrieve_knowledge(db, interview.position, interview.difficulty)
        messages = _build_context(db, interview, knowledge)
        cfg = get_active_llm_config(db)

    client = AsyncOpenAI(base_url=cfg.base_url, api_key=cfg.api_key)
    response = await client.chat.completions.create(
        model=cfg.model, messages=messages, stream=False
    )
    full_response = response.choices[0].message.content or ""

    if full_response:
        with Session(engine) as db:
            save_message(db, interview_id, "interviewer", full_response)

    return response.model_dump()
