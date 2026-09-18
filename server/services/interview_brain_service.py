"""面试官 Brain 服务：把具身交互智能体 SDK 的 LLM 请求代理为「面试官大脑」。

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

# 单轮对话内允许的最大工具调用轮数（防止工具死循环）
MAX_TOOL_ROUNDS = 3


# ---------- Token 管理 ----------

def create_interview_session(
    session: Session,
    user_id: int,
    interview_id: int,
) -> str:
    """为某场面试签发具身交互智能体会话 token。返回 token 字符串。

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
    stage: str = "",
    profile: str = "",
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

## 可用工具与调用规则（重要）
你可以调用工具完成具体动作：读取岗位要求、查看简历、人岗匹配、检索题库、出题、
判题、给回答打分、查询进度、生成报告，以及调整自己的表情与动作。

**必须调用工具（不要用文字敷衍替代）的情形：**
- 候选人明确要求做题、或提到"出题""练一道题" → 调用 `pick_algorithm_problem`
- 面试进行到第 3 轮问答之后，尚未出过算法题 → 调用 `pick_algorithm_problem` 安排一道题
- 候选人表示已提交代码、或要求评测代码 → 调用 `run_code`
- 面试已到收尾阶段（时间不足或你已问完主要问题）→ 调用 `generate_report` 生成报告，再用一两句话告知结果
- 候选人问"你看了我的简历吗"之类 → 调用 `analyze_resume`

**可选调用：**
- 对某段回答想给出量化评价时 → `score_answer`
- 需要核对知识点时 → `retrieve_knowledge`
- 表达对回答的态度时 → `set_emotion`（可附带 `ka` 动作）
- 需要候选人在几个选项里选一个时（开场选方向、连续答不上来、是否进入算法题）→ `offer_choices`；
  候选人点选后系统直接执行对应动作，不需要你再解析他们的选择

调用工具前不要预告细节，用一句话带过即可；工具返回后基于结果继续对话。
**不要每轮都调用工具**，也不要为了展示能力而调用无关工具。
"""
    if jd_text:
        prompt += f"\n## 目标岗位 JD（据此针对性提问与追问）\n{jd_text}\n"
    if interview.focus:
        prompt += f"\n## 本次面试的考察重点（面试官指定，务必覆盖）\n{interview.focus}\n"
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
    if stage:
        from server.services.interview_stage import stage_hint

        hint = stage_hint(stage)
        if hint:
            prompt += f"\n## 当前阶段\n{hint}\n"
    if profile:
        prompt += f"\n{profile}\n"
    return prompt


# ---------- 上下文加载 ----------

async def _retrieve_knowledge(session: Session, interview: Interview) -> str:
    """复用面试编排的 RAG 检索（按归属过滤：全局公开 ∪ 本人私有 ∪ 所在组织知识库）。"""
    from server.services.interview_service import _retrieve_knowledge as _rk

    return await _rk(
        session,
        interview.position,
        interview.difficulty,
        user_id=interview.user_id,
        org_id=interview.org_id,
    )


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
        stage=interview.stage,
        profile=_build_profile_text(session, interview),
    )
    return [{"role": "system", "content": system_prompt}] + _load_messages(session, interview)


def _build_profile_text(session: Session, interview: Interview) -> str:
    """跨会话弱点画像（失败时静默降级，不能影响面试主线）。"""
    try:
        from server.services.profile_service import build_profile_context

        return build_profile_context(session, interview.user_id, interview.position)
    except Exception as e:
        print(f"[Interview Brain] profile context failed: {e}")
        return ""


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


# 工具名 → 过场语：本轮没有正文时先安抚一句，既掩盖工具耗时又触发 Think 姿态
_TOOL_FILLER = {
    "analyze_resume": "我先看一下你的简历。",
    "get_job_description": "我看一下这个岗位的要求。",
    "match_resume_to_jd": "我来对照一下岗位要求。",
    "retrieve_knowledge": "我确认一下这个知识点。",
    "pick_algorithm_problem": "我给你出一道题。",
    "run_code": "我跑一下你的代码。",
    "score_answer": "我评估一下刚才这段回答。",
    "generate_report": "我来整理一下这场面试的报告。",
    "get_interview_progress": "我看一下时间。",
}
_DEFAULT_FILLER = "稍等，我确认一下。"


def _merge_tool_call_delta(acc: dict, deltas) -> None:
    """合并流式 tool_calls 分片（OpenAI 流式下 name/arguments 是分片到达的）。"""
    for d in deltas:
        idx = getattr(d, "index", 0) or 0
        slot = acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
        if getattr(d, "id", None):
            slot["id"] = d.id
        fn = getattr(d, "function", None)
        if fn is not None:
            if getattr(fn, "name", None):
                slot["name"] = fn.name
            if getattr(fn, "arguments", None):
                slot["arguments"] += fn.arguments


def _ka_ssml(ka: str) -> str:
    return (
        "<ue4event><type>ka</type><data>"
        f"<action_semantic>{ka}</action_semantic>"
        "</data></ue4event>"
    )


async def generate_interview_stream(
    user_message: str,
    interview_id: int,
) -> AsyncGenerator[str, None]:
    """面试官流式生成：RAG → LLM（含工具循环）→ 标准 OpenAI SSE。

    同时向事件总线广播结构化事件（tool_start / tool_result / widget / emotion / metrics），
    供前端旁路渲染——这些内容不能混进 SSE 正文字段，否则会被当成播报文本念出来。

    使用独立 session 操作数据库，避免依赖注入的 session 在异步流期间被关闭。
    """
    import time
    import uuid
    from datetime import datetime as dt

    from openai import AsyncOpenAI

    from server.config import settings
    from server.database import engine
    from server.services.common import get_active_llm_config
    from server.services.interview_event_bus import publish
    from server.services.interview_service import save_message
    from server.services.interview_tools import ToolContext, all_tool_schemas, execute_tool

    started_at = time.monotonic()
    chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
    created_ts = int(dt.utcnow().timestamp())

    with Session(engine) as db:
        interview = db.get(Interview, interview_id)
        if not interview:
            print(f"[Interview Brain] Interview {interview_id} not found")
            yield _sse_chunk(chunk_id, created_ts, "", {"content": ""}, "stop")
            yield "data: [DONE]\n\n"
            return

        # 落库候选人回答（_build_context 会一并读出，无需再单独追加）
        save_message(db, interview_id, "user", user_message)

        knowledge = await _retrieve_knowledge(db, interview)
        messages = _build_context(db, interview, knowledge)
        cfg = get_active_llm_config(db)
        ctx = ToolContext(interview_id=interview_id, user_id=interview.user_id or 0)

        # 状态机：语音路径首轮即从「开场」进入「提问」（后续阶段由工具推进）
        from server.services.interview_stage import (
            STAGE_ASK,
            STAGE_OPENING,
            advance_stage,
            normalize_stage,
        )

        if normalize_stage(interview.stage) == STAGE_OPENING:
            advance_stage(db, interview, STAGE_ASK, reason="first_turn")

    client = AsyncOpenAI(base_url=cfg.base_url, api_key=cfg.api_key)
    # 内置工具 + MCP 工具（一次性发现，循环内复用）
    tool_schemas = await all_tool_schemas()

    full_response = ""
    pending_ka: list[str] = []          # 待注入文本的 KA 动作（SSML 开启时生效）
    first_token_at: Optional[float] = None
    tool_ms_total = 0
    tool_times: list[tuple[str, int]] = []   # 单次工具耗时（工具名, 毫秒），用于指标落库

    def emit(text: str) -> str:
        """输出前处理：SSML 注入开关打开时，把待执行的 KA 动作前缀到文本。"""
        nonlocal pending_ka
        if not text:
            return text
        if pending_ka and settings.interview_ssml_inject:
            prefix = "".join(_ka_ssml(k) for k in pending_ka)
            pending_ka = []
            return prefix + text
        return text

    try:
        for round_idx in range(MAX_TOOL_ROUNDS + 1):
            content_buf = ""
            tool_calls: dict = {}

            stream = await client.chat.completions.create(
                model=cfg.model,
                messages=messages,
                tools=tool_schemas,
                tool_choice="auto",
                stream=True,
            )

            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                if delta.content:
                    if first_token_at is None:
                        first_token_at = time.monotonic()
                    content_buf += delta.content
                    full_response += delta.content
                    yield _sse_chunk(chunk_id, created_ts, cfg.model, {"content": emit(delta.content)})

                tool_deltas = getattr(delta, "tool_calls", None)
                if tool_deltas:
                    _merge_tool_call_delta(tool_calls, tool_deltas)

            # 没有工具调用 → 本轮就是最终回答，结束
            if not tool_calls:
                break

            # 超出最大轮数 → 停止工具循环，让 LLM 直接作答
            if round_idx >= MAX_TOOL_ROUNDS:
                print(f"[Interview Brain] max tool rounds reached, interview={interview_id}")
                break

            # 本轮没有正文 → 用按工具名选定的过场语顶上
            if not content_buf.strip():
                names = [tc["name"] for tc in tool_calls.values() if tc.get("name")]
                filler = _TOOL_FILLER.get(names[0], _DEFAULT_FILLER) if names else _DEFAULT_FILLER
                full_response += filler
                yield _sse_chunk(chunk_id, created_ts, cfg.model, {"content": emit(filler)})

            # 把 assistant 的 tool_calls 追加进对话
            messages.append(
                {
                    "role": "assistant",
                    "content": content_buf or None,
                    "tool_calls": [
                        {
                            "id": tc["id"] or f"call_{idx}",
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": tc["arguments"] or "{}"},
                        }
                        for idx, tc in sorted(tool_calls.items())
                    ],
                }
            )

            # 顺序执行工具
            for idx, tc in sorted(tool_calls.items()):
                name = tc.get("name") or ""
                try:
                    args = json.loads(tc["arguments"]) if tc.get("arguments") else {}
                except json.JSONDecodeError:
                    args = {}

                publish(interview_id, {"type": "tool_start", "name": name, "round": round_idx})

                t0 = time.monotonic()
                result = await execute_tool(name, args, ctx)
                cost_ms = int((time.monotonic() - t0) * 1000)
                tool_ms_total += cost_ms
                tool_times.append((name, cost_ms))

                publish(
                    interview_id,
                    {
                        "type": "tool_result",
                        "name": name,
                        "ok": bool(result.get("ok")),
                        "ms": cost_ms,
                    },
                )

                if result.get("widget"):
                    publish(interview_id, {"type": "widget", "payload": result["widget"]})

                data = result.get("data") or {}
                if data.get("act") in ("emotion", "action"):
                    if data.get("ka"):
                        pending_ka.append(str(data["ka"]))
                    publish(
                        interview_id,
                        {
                            "type": "emotion",
                            "emotion": data.get("emotion", ""),
                            "ka": data.get("ka", ""),
                            "reason": data.get("reason", ""),
                        },
                    )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"] or f"call_{idx}",
                        "content": str(result.get("speak", ""))[:4000],
                    }
                )
    except Exception as e:
        print(f"[Interview Brain] Stream error: {e}")
    finally:
        yield _sse_chunk(chunk_id, created_ts, cfg.model, {}, "stop")
        yield "data: [DONE]\n\n"

        # 时延埋点：首字延迟 / 工具总耗时 / 端到端耗时
        ttfa_ms = int((first_token_at - started_at) * 1000) if first_token_at else None
        total_ms = int((time.monotonic() - started_at) * 1000)
        publish(
            interview_id,
            {
                "type": "metrics",
                "ttfaMs": ttfa_ms,
                "toolMs": tool_ms_total,
                "totalMs": total_ms,
            },
        )

        # 指标落库（供 /metrics 页面展示真实实测值）
        try:
            from server.services.metrics_service import record_metrics

            items = [{"kind": "e2e", "valueMs": total_ms}]
            if ttfa_ms is not None:
                items.append({"kind": "ttfa", "valueMs": ttfa_ms})
            items.extend({"kind": "tool", "valueMs": ms, "name": name} for name, ms in tool_times)
            with Session(engine) as db:
                record_metrics(db, interview_id, interview.user_id or 0, items)
        except Exception as e:
            print(f"[Interview Brain] metrics persist failed: {e}")

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
    """面试官非流式生成（SDK 请求 stream=false 时使用）。

    非流式路径同样启用工具，但不做流式工具循环——只执行一轮工具后给出最终回答。
    """
    from openai import AsyncOpenAI

    from server.database import engine
    from server.services.common import get_active_llm_config
    from server.services.interview_event_bus import publish
    from server.services.interview_service import save_message
    from server.services.interview_tools import ToolContext, all_tool_schemas, execute_tool

    with Session(engine) as db:
        interview = db.get(Interview, interview_id)
        if not interview:
            raise ValueError(f"Interview {interview_id} not found")

        # 落库候选人回答（_build_context 会一并读出，无需再单独追加）
        save_message(db, interview_id, "user", user_message)

        knowledge = await _retrieve_knowledge(db, interview)
        messages = _build_context(db, interview, knowledge)
        cfg = get_active_llm_config(db)
        ctx = ToolContext(interview_id=interview_id, user_id=interview.user_id or 0)

    client = AsyncOpenAI(base_url=cfg.base_url, api_key=cfg.api_key)

    response = await client.chat.completions.create(
        model=cfg.model,
        messages=messages,
        tools=await all_tool_schemas(),
        tool_choice="auto",
        stream=False,
    )
    choice = response.choices[0]
    full_response = choice.message.content or ""

    # 一轮工具执行（若有）
    tool_calls = getattr(choice.message, "tool_calls", None)
    if tool_calls:
        messages.append(choice.message.model_dump())
        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                args = {}
            result = await execute_tool(name, args, ctx)
            if result.get("widget"):
                publish(interview_id, {"type": "widget", "payload": result["widget"]})
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": str(result.get("speak", ""))[:4000]}
            )

        follow_up = await client.chat.completions.create(
            model=cfg.model, messages=messages, stream=False
        )
        full_response = follow_up.choices[0].message.content or full_response
        response = follow_up

    if full_response:
        with Session(engine) as db:
            save_message(db, interview_id, "interviewer", full_response)

    return response.model_dump()
