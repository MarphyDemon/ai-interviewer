import json
import random
from datetime import datetime
from typing import Optional
from sqlmodel import Session, select
from server.models import Interview, InterviewMessage, Report, Resume, JobDescription, AlgorithmProblem
from server.services.llm_service import llm_chat
from server.services import offline_service, org_service
from server.services.rag_service import search
from server.services.interview_stage import (
    STAGE_FINISHED,
    STAGE_REPORT,
    advance_by_action,
    advance_stage,
    stage_hint,
    stage_payload,
)
from server.services.profile_service import build_profile_context, refresh_profile_from_report
from server.embedding.siliconflow import get_embedding


# ---------- 难度词汇归一化 ----------
# 三套词汇并存：前端 i18n 用 junior/mid/senior；面试报告与题库筛选用 初级/中级/高级；
# 算法题（AlgorithmProblem.difficulty）用 简单/中等/困难。这里统一收口，避免互相匹配不上。
_DIFFICULTY_ALIASES = {
    "junior": "初级",
    "初级": "初级",
    "mid": "中级",
    "中级": "中级",
    "senior": "高级",
    "高级": "高级",
    "简单": "初级",
    "中等": "中级",
    "困难": "高级",
}
_PROBLEM_DIFFICULTY = {"初级": "简单", "中级": "中等", "高级": "困难"}


def normalize_difficulty(value: str) -> str:
    """把面试难度统一为中文（初级 / 中级 / 高级）。无法识别时原样返回。"""
    raw = (value or "").strip()
    if not raw:
        return "中级"
    return _DIFFICULTY_ALIASES.get(raw, _DIFFICULTY_ALIASES.get(raw.lower(), raw))


def problem_difficulty_of(value: str) -> str:
    """把面试难度换算为算法题难度词汇（简单 / 中等 / 困难）。无法识别时返回空串（表示不过滤）。"""
    return _PROBLEM_DIFFICULTY.get(normalize_difficulty(value), "")


async def generate_first_question(
    session: Session,
    interview: Interview,
    resume: Optional[Resume] = None,
    jd: Optional[JobDescription] = None,
    lang: str = "en",
) -> dict:
    knowledge_context = await _retrieve_knowledge(
        session,
        interview.position,
        interview.difficulty,
        user_id=interview.user_id,
        org_id=interview.org_id,
    )

    resume_text = ""
    if resume:
        resume_text = resume.parsed_text[:2000]

    jd_text = ""
    if jd:
        jd_text = jd.content[:3000]

    system_prompt = _build_system_prompt(
        position=interview.position,
        difficulty=interview.difficulty,
        style=interview.style,
        knowledge=knowledge_context,
        resume_text=resume_text,
        jd_text=jd_text,
        focus_text=interview.focus,
        lang=lang,
        stage=interview.stage,
        profile=build_profile_context(session, interview.user_id, interview.position),
    )

    user_prompt = "请开始面试，提出第一个问题。" if lang == "zh" else "Start the interview. Ask the first question."

    result = await llm_chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        session=session,
        json_mode=True,
    )

    return _parse_ai_response(result)


async def process_answer(
    session: Session,
    interview: Interview,
    answer: str,
) -> dict:
    messages = _load_conversation(session, interview.id)
    messages.append({"role": "user", "content": answer})

    remaining = _check_remaining_time(interview)

    knowledge_context = await _retrieve_knowledge(
        session,
        interview.position,
        interview.difficulty,
        user_id=interview.user_id,
        org_id=interview.org_id,
    )

    jd_text = ""
    if interview.jd_id:
        jd = session.get(JobDescription, interview.jd_id)
        if jd:
            jd_text = jd.content[:3000]

    system_prompt = _build_system_prompt(
        position=interview.position,
        difficulty=interview.difficulty,
        style=interview.style,
        knowledge=knowledge_context,
        jd_text=jd_text,
        focus_text=interview.focus,
        stage=interview.stage,
        profile=build_profile_context(session, interview.user_id, interview.position),
    )

    if remaining <= 0:
        messages.append({
            "role": "system",
            "content": "面试时间已到，请结束面试。action 设为 end。",
        })

    result = await llm_chat(
        [{"role": "system", "content": system_prompt}] + messages,
        session=session,
        json_mode=True,
    )

    parsed = _parse_ai_response(result)
    # 状态机：按 LLM 返回的 action 推进阶段（choices 等不改变阶段的 action 会被忽略）
    advance_by_action(session, interview, parsed.get("action"))
    return parsed


async def generate_report(session: Session, interview: Interview) -> Report:
    # 状态机：进入报告阶段（强制收敛，允许从任意阶段跳入）
    advance_stage(session, interview, STAGE_REPORT, reason="report", force=True)

    messages = _load_conversation(session, interview.id)
    resume = session.get(Resume, interview.resume_id) if interview.resume_id else None
    jd = session.get(JobDescription, interview.jd_id) if interview.jd_id else None
    knowledge = await _retrieve_knowledge(
        session,
        interview.position,
        interview.difficulty,
        user_id=interview.user_id,
        org_id=interview.org_id,
    )

    conversation_text = "\n".join(
        [f"{'Interviewer' if m['role'] == 'assistant' else 'Candidate'}: {m['content']}" for m in messages]
    )

    jd_text = jd.content[:3000] if jd else ""
    match_section = ""
    if jd_text:
        match_section = """
  "matchScore": 0-100的整数（候选人对该 JD 的整体匹配度）,
  "matchBreakdown": [{"requirement": "JD中明确列出的某条要求", "status": "met|partial|gap", "evidence": "依据候选人答题或简历的简短证据"}],
"""
    match_instruction = ""
    if jd_text:
        match_instruction = """
Additional requirement — produce a structured person-job match against the JD:
- "matchScore": 0-100 integer, overall fit for THIS specific JD.
- "matchBreakdown": one entry per KEY requirement explicitly listed in the JD. status ∈ met(满足)/partial(部分)/gap(不足). evidence must reference the candidate's answers or resume.
- "jobFit": a concise overall summary of fit + main gaps + recommendation.
"""
    else:
        match_instruction = '\n- "jobFit": a concise overall job-fit assessment text.'

    prompt = f"""Based on the interview transcript below, generate a comprehensive review report. Output JSON:
{{
  "totalScore": 0-100,
  "dimensionScores": [{{"label": "Technical Knowledge", "score": 0}}, {{"label": "Communication", "score": 0}}, {{"label": "Job Fit", "score": 0}}, {{"label": "Problem Solving", "score": 0}}, {{"label": "Technical Depth", "score": 0}}],
  "summary": "Overall summary text",
  "perQuestionReviews": [{{"question": "...", "answer": "...", "review": "...", "referenceAnswer": "...", "score": 0}}],
  "resumeReview": {{"structureScore": 0, "positionMatch": 0, "highlights": [], "weaknesses": []}},{match_section}
  "jobFit": "Job fit assessment text"
}}
{match_instruction}

Interview transcript:
{conversation_text}

Reference knowledge:
{knowledge[:2000]}

Resume (if available):
{resume.parsed_text[:2000] if resume else 'N/A'}

Job Description (if available):
{jd_text if jd_text else 'N/A'}
"""

    result = await llm_chat(
        [
            {"role": "system", "content": "You are an interview evaluation expert. Output strictly in JSON format."},
            {"role": "user", "content": prompt},
        ],
        session=session,
        json_mode=True,
    )

    try:
        start = result.find("{")
        end = result.rfind("}") + 1
        data = json.loads(result[start:end]) if start >= 0 and end > start else {}
    except json.JSONDecodeError:
        data = {}

    match_score = data.get("matchScore") if jd_text else None
    match_breakdown = (
        json.dumps(data.get("matchBreakdown", []), ensure_ascii=False) if jd_text else "[]"
    )

    report = Report(
        interview_id=interview.id,
        total_score=data.get("totalScore", 0),
        dimension_scores=json.dumps(data.get("dimensionScores", []), ensure_ascii=False),
        summary=data.get("summary", ""),
        per_question_reviews=json.dumps(data.get("perQuestionReviews", []), ensure_ascii=False),
        resume_review=json.dumps(data.get("resumeReview", {}), ensure_ascii=False),
        job_fit=data.get("jobFit", ""),
        match_score=match_score,
        match_breakdown=match_breakdown,
    )
    session.add(report)

    interview.status = "已结束"
    interview.ended_at = datetime.utcnow()
    session.add(interview)
    session.commit()
    session.refresh(report)

    # 跨会话画像：把本场报告的弱点聚合进用户画像，供下一场面试的 prompt 注入
    try:
        refresh_profile_from_report(session, interview, report)
    except Exception as e:
        print(f"[Profile] refresh failed: {e}")

    advance_stage(session, interview, STAGE_FINISHED, reason="finished", force=True)

    return report


async def _retrieve_knowledge(
    session: Session,
    position: str,
    difficulty: str,
    *,
    user_id: Optional[int] = None,
    org_id: Optional[int] = None,
) -> str:
    """检索本场面试可用的知识素材：全局公开 ∪ 本人私有 ∪ 所在组织知识库。

    向量库的 chunk 上没有归属元数据，因此以数据库为权威做二次过滤，
    避免私有或他人组织的知识被检索到（存量数据无需重建索引）。
    """
    allowed = org_service.visible_knowledge_doc_ids(session, user_id, org_id)
    if not allowed:
        return ""

    query_text = f"{position} {difficulty} 面试题"
    if offline_service.enabled():
        # 离线规则模式：关键词检索（无向量化）
        return "\n---\n".join(
            offline_service.keyword_search(
                session, query_text, top_k=5, position=position, doc_ids=allowed
            )
        )
    try:
        embedding = await get_embedding(query_text)
        # 先尝试按 position 过滤，没结果则全库搜索；
        # 多取候选片段（20 条），按归属过滤后再截断到 5 条
        candidates: list[dict] = []
        if position:
            candidates = search(embedding, top_k=20, where={"position": position})
        if not candidates:
            candidates = search(embedding, top_k=20)
        results = org_service.filter_visible_chunks(candidates, allowed)[:5]
        return "\n---\n".join([r["content"] for r in results])
    except Exception as e:
        print(f"[RAG] retrieval failed: {e}")
        return ""


def _build_system_prompt(
    position: str,
    difficulty: str,
    style: str,
    knowledge: str = "",
    resume_text: str = "",
    jd_text: str = "",
    focus_text: str = "",
    lang: str = "en",
    stage: str = "",
    profile: str = "",
) -> str:
    if lang == "zh":
        prompt = f"""你是一名{style}风格的面试官，正在面试{position}方向的{difficulty}级别候选人。

规则：
1. 每次只提一个问题
2. 根据候选人回答质量决定是否追问（最多2层追问）
3. 追问要深入细节，考察真实理解
4. 如有简历信息，可针对性提问项目经历
5. 覆盖该岗位的核心知识点，包括基础概念、项目经验、系统设计等
6. 如有岗位 JD，需针对 JD 中明确列出的技术栈、能力要求、职责进行提问与追问，考察候选人对该具体岗位的匹配度
7. 在面试中段（非首题非末题），可适当安排 1-2 道算法/编码题，考察 coding 能力。使用 action="algorithm"

输出格式（严格JSON）：
{{"action": "ask|followup|next_question|algorithm|choices|end", "content": "你的提问内容", "reasoning": "内部判断", "choices": [{{"label": "选项文案", "intent": "skip_question|hint|start_algorithm|end_interview"}}]}}

action 说明：
- ask: 首次提问
- followup: 追问（同一题的深入）
- next_question: 换新题
- algorithm: 安排一道算法编码题（系统会自动选题，content 写引导语即可）
- choices: 需要候选人做选择时使用（如开场选择方向、连续答不上来、询问是否进入算法题），把 2~4 个选项放进 choices，候选人点选后系统直接执行，不再经过你
- end: 面试结束
"""
    else:
        prompt = f"""You are a {style} interviewer conducting a {difficulty}-level interview for a {position} position.

Rules:
1. Ask only one question at a time
2. Decide whether to follow up based on answer quality (max 2 follow-up levels)
3. Follow-ups should probe details to test real understanding
4. If resume info is available, ask targeted questions about project experience
5. Cover core knowledge areas: fundamentals, project experience, system design, etc.
6. If a job description (JD) is provided, ask and follow up on the specific tech stack, capabilities and responsibilities explicitly listed in the JD, to assess the candidate's fit for this particular role.
7. In the middle of the interview (not first or last question), you may assign 1-2 algorithm/coding questions to test coding ability. Use action="algorithm".

Output format (strict JSON):
{{"action": "ask|followup|next_question|algorithm|choices|end", "content": "your question", "reasoning": "internal judgment", "choices": [{{"label": "option text", "intent": "skip_question|hint|start_algorithm|end_interview"}}]}}

Action meanings:
- ask: first question
- followup: deeper follow-up on the same question
- next_question: switch to a new question
- algorithm: assign an algorithm/coding problem (system auto-selects, just write intro in content)
- choices: when the candidate should pick an option (opening direction, repeated failures, whether to enter a coding round) — put 2-4 options in "choices"; the system executes the selection directly without you
- end: interview ended
"""
    if jd_text:
        prompt += f"\n目标岗位 JD（据此针对性提问与追问）：\n{jd_text}\n"
    if focus_text:
        if lang == "zh":
            prompt += f"\n本次面试的考察重点（面试官指定，务必覆盖）：\n{focus_text}\n"
        else:
            prompt += f"\nFocus areas required by the interviewer (must be covered):\n{focus_text}\n"
    if knowledge:
        prompt += f"\n参考知识素材（可据此出题和判卷）：\n{knowledge}\n"
    if resume_text:
        prompt += f"\n候选人简历：\n{resume_text}\n"
    if stage:
        hint = stage_hint(stage)
        if hint:
            prompt += f"\n{hint}\n"
    if profile:
        prompt += f"\n{profile}\n"
    return prompt


def _parse_ai_response(raw: str) -> dict:
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except json.JSONDecodeError:
        pass
    return {"action": "next_question", "content": raw, "reasoning": ""}


def _load_conversation(session: Session, interview_id: int) -> list[dict]:
    msgs = session.exec(
        select(InterviewMessage).where(InterviewMessage.interview_id == interview_id)
    ).all()
    return [
        {"role": "assistant" if m.role == "interviewer" else "user", "content": m.content}
        for m in msgs
    ]


def _check_remaining_time(interview: Interview) -> int:
    if not interview.started_at:
        return 0
    elapsed = (datetime.utcnow() - interview.started_at).total_seconds()
    remaining = interview.duration * 60 - elapsed
    return int(remaining)


def save_message(
    session: Session,
    interview_id: int,
    role: str,
    content: str,
    question_index: int = 0,
    followup_level: int = 0,
):
    msg = InterviewMessage(
        interview_id=interview_id,
        role=role,
        content=content,
        question_index=question_index,
        followup_level=followup_level,
    )
    session.add(msg)
    session.commit()


def pick_algorithm_problem(session: Session, difficulty: str = "") -> Optional[AlgorithmProblem]:
    """根据难度选取一道算法题（随机，无则返回 None）。

    入参可能是面试难度（junior/mid/senior，或历史数据里的中文写法），
    需先换算成算法题自己的难度词汇（简单/中等/困难），否则永远匹配不上而退化为全库随机。
    """
    stmt = select(AlgorithmProblem).where(AlgorithmProblem.is_public == True)  # noqa: E712
    problem_difficulty = problem_difficulty_of(difficulty)
    if problem_difficulty:
        stmt = stmt.where(AlgorithmProblem.difficulty == problem_difficulty)
    rows = session.exec(stmt).all()
    if not rows:
        # 退而求其次，取全部
        rows = session.exec(select(AlgorithmProblem).where(AlgorithmProblem.is_public == True)).all()  # noqa: E712
    if not rows:
        return None
    return random.choice(rows)


def format_problem_for_interview(problem: AlgorithmProblem) -> dict:
    """将算法题格式化为面试前端可用的结构（不含隐藏测试用例）。"""
    return {
        "id": problem.id,
        "title": problem.title,
        "description": problem.description,
        "difficulty": problem.difficulty,
        "tags": json.loads(problem.tags) if problem.tags else [],
        "examples": json.loads(problem.examples) if problem.examples else [],
        "timeLimitMs": problem.time_limit_ms,
        "memoryLimitMb": problem.memory_limit_mb,
    }


async def start_interview_session(
    session: Session,
    *,
    user_id: int,
    position: str,
    difficulty: str,
    duration: int = 30,
    style: str = "friendly",
    resume_id: Optional[int] = None,
    jd_id: Optional[int] = None,
    lang: str = "en",
    org_id: Optional[int] = None,
    focus: str = "",
) -> dict:
    """创建一场面试并生成首题。

    个人练习（/api/interview/start）与候选人邀请（/api/invite/{token}/start）共用本函数，
    避免两条链路在「状态机推进 / 首题落库 / 算法题附带」这些细节上逐渐漂移。
    org_id / focus 仅在候选人邀请场景传入：前者把面试归属到企业组织，
    后者是 HR 指定的考察重点，会注入每一轮的面试 prompt。
    """
    interview = Interview(
        user_id=user_id,
        resume_id=resume_id,
        jd_id=jd_id,
        org_id=org_id,
        position=position,
        # 前端传 junior/mid/senior，统一落库为中文难度（初级/中级/高级）
        difficulty=normalize_difficulty(difficulty),
        duration=duration,
        style=style,
        focus=(focus or "").strip()[:2000],
    )
    session.add(interview)
    session.commit()
    session.refresh(interview)

    resume = session.get(Resume, resume_id) if resume_id else None
    jd = session.get(JobDescription, jd_id) if jd_id else None

    first = await generate_first_question(session, interview, resume, jd=jd, lang=lang)

    # 状态机：开场 → 按首个 action 落到「提问 / 算法题」等阶段
    advance_by_action(session, interview, first.get("action"))

    save_message(
        session, interview.id, "interviewer", first.get("content", ""),
        question_index=1, followup_level=0,
    )

    first_question = {
        "action": first.get("action", "ask"),
        "content": first.get("content", ""),
        "reasoning": first.get("reasoning", ""),
    }

    # 如果首题是算法题，附带题目详情
    if first.get("action") == "algorithm":
        problem = pick_algorithm_problem(session, interview.difficulty)
        if problem:
            first_question["problem"] = format_problem_for_interview(problem)

    # 交互控件：LLM 在开场让候选人做选择时下发可点选项
    choices = first.get("choices") or []
    if choices:
        first_question["choices"] = choices

    return {
        "interview": interview,
        "firstQuestion": first_question,
        "stage": stage_payload(interview.stage),
    }

