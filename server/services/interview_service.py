import json
from datetime import datetime
from typing import Optional
from sqlmodel import Session, select
from server.models import Interview, InterviewMessage, Report, Resume, KnowledgeDoc, JobDescription
from server.services.llm_service import llm_chat
from server.services.rag_service import search
from server.embedding.siliconflow import get_embedding


async def generate_first_question(
    session: Session,
    interview: Interview,
    resume: Optional[Resume] = None,
    jd: Optional[JobDescription] = None,
    lang: str = "en",
) -> dict:
    knowledge_context = await _retrieve_knowledge(session, interview.position, interview.difficulty)

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
        lang=lang,
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

    knowledge_context = await _retrieve_knowledge(session, interview.position, interview.difficulty)

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

    return _parse_ai_response(result)


async def generate_report(session: Session, interview: Interview) -> Report:
    messages = _load_conversation(session, interview.id)
    resume = session.get(Resume, interview.resume_id) if interview.resume_id else None
    jd = session.get(JobDescription, interview.jd_id) if interview.jd_id else None
    knowledge = await _retrieve_knowledge(session, interview.position, interview.difficulty)

    conversation_text = "\n".join(
        [f"{'Interviewer' if m['role'] == 'assistant' else 'Candidate'}: {m['content']}" for m in messages]
    )

    jd_text = jd.content[:3000] if jd else ""
    match_section = ""
    if jd_text:
        match_section = f"""
  "matchScore": 0-100的整数（候选人对该 JD 的整体匹配度）,
  "matchBreakdown": [{{"requirement": "JD中明确列出的某条要求", "status": "met|partial|gap", "evidence": "依据候选人答题或简历的简短证据"}}],
"""
    match_instruction = ""
    if jd_text:
        match_instruction = f"""
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

    return report


async def _retrieve_knowledge(session: Session, position: str, difficulty: str) -> str:
    query_text = f"{position} {difficulty} 面试题"
    try:
        embedding = await get_embedding(query_text)
        # 先尝试按 position 过滤，没结果则全库搜索
        results = []
        if position:
            results = search(embedding, top_k=5, where={"position": position})
        if not results:
            results = search(embedding, top_k=5)
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
    lang: str = "en",
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

输出格式（严格JSON）：
{{"action": "ask|followup|next_question|end", "content": "你的提问内容", "reasoning": "内部判断"}}

action 说明：
- ask: 首次提问
- followup: 追问（同一题的深入）
- next_question: 换新题
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

Output format (strict JSON):
{{"action": "ask|followup|next_question|end", "content": "your question", "reasoning": "internal judgment"}}

Action meanings:
- ask: first question
- followup: deeper follow-up on the same question
- next_question: switch to a new question
- end: interview ended
"""
    if jd_text:
        prompt += f"\n目标岗位 JD（据此针对性提问与追问）：\n{jd_text}\n"
    if knowledge:
        prompt += f"\n参考知识素材（可据此出题和判卷）：\n{knowledge}\n"
    if resume_text:
        prompt += f"\n候选人简历：\n{resume_text}\n"
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
