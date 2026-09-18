"""面试 Function Calling 工具注册表。

设计约定：
- `TOOL_SCHEMAS` 为 OpenAI tools 格式，直接透传给 LLM。
- `execute_tool` 统一返回 `{ok, speak, widget, data}`：
    - `speak`  : 回灌给 LLM 的工具结果文本（role=tool 的 content），由 LLM 决定怎么讲
    - `widget` : 需要前端渲染的 Widget 载荷（可为 None）
    - `data`   : 供 brain 服务消费的附加信息（如情绪/动作注入指令）
- 每次调用自行开启 `Session(engine)`，避免复用流式期间可能已关闭的会话。
"""
import json
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from sqlmodel import Session, select

from server.models import (
    AlgorithmProblem,
    CodeSubmission,
    Interview,
    JobDescription,
    Resume,
)


@dataclass
class ToolContext:
    interview_id: int
    user_id: int


# ---------- 工具 Schema ----------

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_job_description",
            "description": "获取本次面试目标岗位的 JD 原文，用于针对性提问与追问。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_resume",
            "description": "读取候选人简历的解析结果与亮点/短板分析，用于针对性提问项目经历。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "match_resume_to_jd",
            "description": "把候选人简历与目标岗位 JD 做结构化匹配，输出匹配度与逐条差距。通常在面试收尾阶段调用。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_knowledge",
            "description": "按关键词检索题库素材，用于校验答案或构造更深入的追问。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索关键词或问题"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pick_algorithm_problem",
            "description": "抽取一道算法题并展示给候选人。调用后请用口播说明题意，然后等待候选人作答。",
            "parameters": {
                "type": "object",
                "properties": {
                    "difficulty": {
                        "type": "string",
                        "enum": ["简单", "中等", "困难"],
                        "description": "题目难度，缺省则与面试难度一致",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_code",
            "description": "对指定的算法题运行判题并返回用例结果。未提供代码时使用该候选人最近一次提交。",
            "parameters": {
                "type": "object",
                "properties": {
                    "problem_id": {"type": "integer", "description": "题目 ID"},
                    "language": {"type": "string", "description": "编程语言，如 python"},
                    "code": {"type": "string", "description": "候选人代码，缺省则取最近一次提交"},
                },
                "required": ["problem_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "score_answer",
            "description": "对候选人的一次回答做快速打分与简评，用于生成即时反馈。",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "被回答的问题"},
                    "answer": {"type": "string", "description": "候选人的回答原文"},
                },
                "required": ["question", "answer"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_interview_progress",
            "description": "查询本场面试的进度：已提问轮数、剩余时间。用于把握节奏。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report",
            "description": "结束面试并生成完整体检报告。仅在确认面试应当结束时调用。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_emotion",
            "description": (
                "设置面试官本轮的态度：情绪表情 + 可选关键动作。"
                "用于表达对候选人回答的评价（赞许/疑惑/严肃等），让反馈更有温度。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "emotion": {
                        "type": "string",
                        "description": "情绪标签，需属于当前音色支持的情感集合",
                    },
                    "ka": {
                        "type": "string",
                        "description": "可选，关键动作语义名（如点头、示意类动作）",
                    },
                    "reason": {"type": "string", "description": "选择该情绪的内部依据"},
                },
                "required": ["emotion"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_action",
            "description": "触发一个关键动作（关键动作库中的语义名），用于强调、示意或过渡。",
            "parameters": {
                "type": "object",
                "properties": {
                    "ka": {"type": "string", "description": "关键动作语义名"},
                },
                "required": ["ka"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "offer_choices",
            "description": (
                "给候选人一组可点选的选项（如换题目/跳过此题/看提示/进入算法题/结束面试）。"
                "候选人点选后系统直接执行对应动作，不需要你再解析他们的选择。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "选项组标题，如「接下来你想…」"},
                    "options": {
                        "type": "array",
                        "description": "2-4 个选项",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string", "description": "选项文案"},
                                "intent": {
                                    "type": "string",
                                    "enum": [
                                        "skip_question",
                                        "hint",
                                        "start_algorithm",
                                        "end_interview",
                                    ],
                                    "description": "点选后系统执行的确定性动作",
                                },
                            },
                            "required": ["label", "intent"],
                        },
                    },
                },
                "required": ["options"],
            },
        },
    },
]


# 交互控件允许的确定性意图（与前端 PickerWidget / /command 端点一一对应）
CHOICE_INTENTS: tuple[str, ...] = (
    "skip_question",
    "hint",
    "start_algorithm",
    "end_interview",
)


def build_choices_widget(title: str, options: list[dict], widget_id: str = "") -> dict:
    """构造交互控件（Picker）Widget 载荷。

    工具、文字路径路由、/command 端点共用同一份结构，避免三处各写一遍。
    """
    normalized: list[dict] = []
    for opt in options or []:
        if not isinstance(opt, dict):
            continue
        label = str(opt.get("label") or "").strip()
        intent = str(opt.get("intent") or "").strip()
        if not label or intent not in CHOICE_INTENTS:
            continue
        normalized.append({"label": label, "intent": intent, "value": intent})
    if not normalized:
        return {}
    return {
        "type": "picker",
        "id": widget_id or f"picker-{uuid.uuid4().hex[:8]}",
        "data": {"title": title or "请选择", "options": normalized},
        "ttl": 180000,
    }


async def all_tool_schemas() -> list[dict]:
    """内置工具 + 已启用的 MCP 工具，供 LLM 一次性看到全部可调用能力。

    MCP 不可用（未配置 / 子进程启动失败）时静默退化为内置工具，不影响面试主线。
    """
    schemas = list(TOOL_SCHEMAS)
    try:
        from server.services.mcp_service import list_openai_tools

        schemas.extend(await list_openai_tools())
    except Exception as e:
        print(f"[Interview Tools] MCP tool discovery failed: {e}")
    return schemas


# ---------- 内部工具函数 ----------

async def _llm_json_async(prompt: str, system: str) -> dict:
    """异步调用 LLM 并解析 JSON。"""
    from server.services.llm_service import llm_chat

    raw = await llm_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        json_mode=True,
    )
    start, end = raw.find("{"), raw.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            return {}
    return {}


def _get_interview(session: Session, ctx: ToolContext) -> Optional[Interview]:
    interview = session.get(Interview, ctx.interview_id)
    if not interview or interview.user_id != ctx.user_id:
        return None
    return interview


# ---------- 工具实现 ----------

async def _tool_get_job_description(session: Session, ctx: ToolContext, args: dict) -> dict:
    interview = _get_interview(session, ctx)
    if not interview or not interview.jd_id:
        return {"ok": False, "speak": "本场面试未关联岗位 JD。", "widget": None, "data": {}}

    jd = session.get(JobDescription, interview.jd_id)
    if not jd:
        return {"ok": False, "speak": "未找到岗位 JD。", "widget": None, "data": {}}

    return {
        "ok": True,
        "speak": f"岗位「{jd.title}」要求如下：\n{jd.content[:1500]}",
        "widget": None,
        "data": {"jdId": jd.id, "title": jd.title},
    }


async def _tool_analyze_resume(session: Session, ctx: ToolContext, args: dict) -> dict:
    interview = _get_interview(session, ctx)
    if not interview or not interview.resume_id:
        return {"ok": False, "speak": "本场面试未关联简历。", "widget": None, "data": {}}

    resume = session.get(Resume, interview.resume_id)
    if not resume:
        return {"ok": False, "speak": "未找到简历。", "widget": None, "data": {}}

    try:
        analysis = json.loads(resume.analysis_result or "{}")
    except json.JSONDecodeError:
        analysis = {}

    highlights = analysis.get("highlights", [])
    weaknesses = analysis.get("weaknesses", [])

    speak = f"简历要点：结构分 {analysis.get('structureScore', '-')}，岗位匹配 {analysis.get('positionMatch', '-')}。"
    if highlights:
        speak += "\n亮点：" + "；".join(str(h) for h in highlights[:4])
    if weaknesses:
        speak += "\n待确认：" + "；".join(str(w) for w in weaknesses[:4])

    return {
        "ok": True,
        "speak": speak,
        "widget": {
            "type": "resume_highlight",
            "id": f"resume-{resume.id}",
            "data": {
                "filename": resume.filename,
                "structureScore": analysis.get("structureScore"),
                "positionMatch": analysis.get("positionMatch"),
                "highlights": highlights,
                "weaknesses": weaknesses,
            },
        },
        "data": {"resumeId": resume.id},
    }


async def _tool_match_resume_to_jd(session: Session, ctx: ToolContext, args: dict) -> dict:
    interview = _get_interview(session, ctx)
    if not interview:
        return {"ok": False, "speak": "面试不存在。", "widget": None, "data": {}}
    if not interview.resume_id or not interview.jd_id:
        return {
            "ok": False,
            "speak": "缺少简历或岗位 JD，无法做匹配分析。",
            "widget": None,
            "data": {},
        }

    resume = session.get(Resume, interview.resume_id)
    jd = session.get(JobDescription, interview.jd_id)
    if not resume or not jd:
        return {"ok": False, "speak": "简历或 JD 缺失。", "widget": None, "data": {}}

    prompt = f"""请把候选人简历与目标岗位 JD 做结构化匹配。输出 JSON：
{{
  "matchScore": 0-100 的整数,
  "matchBreakdown": [{{"requirement": "JD 中明确列出的要求", "status": "met|partial|gap", "evidence": "来自简历的简短证据"}}],
  "jobFit": "整体匹配情况与主要差距的简短结论"
}}

岗位 JD：
{jd.content[:3000]}

候选人简历：
{resume.parsed_text[:3000]}
"""
    data = await _llm_json_async(
        prompt, "你是资深招聘专家，输出严格的 JSON。"
    )

    score = data.get("matchScore")
    breakdown = data.get("matchBreakdown", [])
    job_fit = data.get("jobFit", "")

    gaps = [b for b in breakdown if isinstance(b, dict) and b.get("status") == "gap"]
    speak = f"人岗匹配度 {score} 分。{job_fit}"
    if gaps:
        speak += "\n主要差距：" + "；".join(str(g.get("requirement", "")) for g in gaps[:3])

    return {
        "ok": True,
        "speak": speak,
        "widget": {
            "type": "match_score",
            "id": f"match-{interview.id}",
            "data": {"matchScore": score, "matchBreakdown": breakdown, "jobFit": job_fit},
        },
        "data": {"matchScore": score},
    }


async def _tool_retrieve_knowledge(session: Session, ctx: ToolContext, args: dict) -> dict:
    from server.services.interview_service import _retrieve_knowledge

    query = str(args.get("query", "")).strip()
    interview = _get_interview(session, ctx)
    position = interview.position if interview else ""
    difficulty = interview.difficulty if interview else ""

    knowledge = await _retrieve_knowledge(
        session,
        query or position,
        difficulty,
        user_id=interview.user_id if interview else None,
        org_id=interview.org_id if interview else None,
    )
    if not knowledge:
        return {"ok": False, "speak": "题库中未检索到相关素材。", "widget": None, "data": {}}

    return {
        "ok": True,
        "speak": knowledge[:1200],
        "widget": None,
        "data": {"chars": len(knowledge)},
    }


async def _tool_pick_algorithm_problem(session: Session, ctx: ToolContext, args: dict) -> dict:
    from server.services.interview_service import (
        format_problem_for_interview,
        pick_algorithm_problem,
    )

    interview = _get_interview(session, ctx)
    difficulty = str(args.get("difficulty") or (interview.difficulty if interview else ""))
    problem = pick_algorithm_problem(session, difficulty)
    if not problem:
        return {"ok": False, "speak": "题库中没有可用题目。", "widget": None, "data": {}}

    formatted = format_problem_for_interview(problem)
    speak = f"题目《{problem.title}》（{problem.difficulty}）：{problem.description[:300]}"

    if interview:
        from server.services.interview_stage import STAGE_ALGORITHM, advance_stage

        advance_stage(session, interview, STAGE_ALGORITHM, reason="tool:pick_algorithm_problem")

    return {
        "ok": True,
        "speak": speak,
        "widget": {
            "type": "question_card",
            "id": f"problem-{problem.id}",
            "data": formatted,
            "ttl": 600000,
        },
        "data": {"problemId": problem.id},
    }


async def _tool_run_code(session: Session, ctx: ToolContext, args: dict) -> dict:
    from server.services.judge_service import judge

    problem_id = args.get("problem_id")
    if not isinstance(problem_id, int):
        return {"ok": False, "speak": "缺少题目 ID。", "widget": None, "data": {}}

    problem = session.get(AlgorithmProblem, problem_id)
    if not problem:
        return {"ok": False, "speak": f"题目 {problem_id} 不存在。", "widget": None, "data": {}}

    language = str(args.get("language") or "python")
    code = args.get("code")

    if not code:
        # 未提供代码时，取该用户对该题最近一次提交
        latest = session.exec(
            select(CodeSubmission)
            .where(
                CodeSubmission.user_id == ctx.user_id,
                CodeSubmission.problem_id == problem_id,
            )
            .order_by(CodeSubmission.created_at.desc())
        ).first()
        if not latest:
            return {
                "ok": False,
                "speak": "候选人尚未提交代码，无法判题。",
                "widget": None,
                "data": {},
            }
        code = latest.code
        language = latest.language

    test_cases = json.loads(problem.test_cases) if problem.test_cases else []
    if not test_cases:
        return {"ok": False, "speak": "该题没有测试用例。", "widget": None, "data": {}}

    result = await judge(test_cases, language, code)

    passed = result.status == "accepted"
    speak = f"判题结果：{result.status}（通过 {result.pass_count}/{result.total_count}）。"
    if not passed and result.compile_error:
        speak += f"\n编译错误：{result.compile_error[:300]}"
    if not passed:
        failed = next((c for c in result.cases if not c.passed), None)
        if failed:
            speak += f"\n首个失败用例：输入 {failed.input}，期望 {failed.expected}，实际 {failed.actual}"

    interview = _get_interview(session, ctx)
    if interview:
        from server.services.interview_stage import STAGE_JUDGE, advance_stage

        advance_stage(session, interview, STAGE_JUDGE, reason="tool:run_code")

    return {
        "ok": True,
        "speak": speak,
        "widget": {
            "type": "judge_result",
            "id": f"judge-{problem_id}",
            "data": {
                "title": problem.title,
                "status": result.status,
                "passCount": result.pass_count,
                "totalCount": result.total_count,
                "durationMs": result.duration_ms,
                "compileError": result.compile_error,
                "cases": [
                    {
                        "passed": c.passed,
                        "input": c.input,
                        "expected": c.expected,
                        "actual": c.actual,
                    }
                    for c in result.cases
                ],
            },
        },
        "data": {"problemId": problem_id, "accepted": passed},
    }


async def _tool_score_answer(session: Session, ctx: ToolContext, args: dict) -> dict:
    question = str(args.get("question", "")).strip()
    answer = str(args.get("answer", "")).strip()
    if not answer:
        return {"ok": False, "speak": "没有可评分的回答。", "widget": None, "data": {}}

    prompt = f"""请对候选人的回答做快速评估。输出 JSON：
{{
  "score": 0-100 的整数,
  "verdict": "一句话结论（不超过 30 字）",
  "strengths": ["最多 2 条优点"],
  "gaps": ["最多 2 条不足"]
}}

问题：{question or "（未提供）"}
候选人回答：{answer[:2000]}
"""
    data = await _llm_json_async(prompt, "你是严格但公正的技术面试官，输出严格 JSON。")

    score = data.get("score")
    return {
        "ok": True,
        "speak": f"本次回答评分 {score} 分。{data.get('verdict', '')}",
        "widget": {
            "type": "score",
            "id": f"score-{abs(hash(answer)) % 100000}",
            "data": data,
            "ttl": 20000,
        },
        "data": {"score": score},
    }


async def _tool_get_interview_progress(session: Session, ctx: ToolContext, args: dict) -> dict:
    from server.models import InterviewMessage

    interview = _get_interview(session, ctx)
    if not interview:
        return {"ok": False, "speak": "面试不存在。", "widget": None, "data": {}}

    asked = len(
        session.exec(
            select(InterviewMessage).where(
                InterviewMessage.interview_id == interview.id,
                InterviewMessage.role == "interviewer",
            )
        ).all()
    )
    from server.services.interview_service import _check_remaining_time
    from server.services.interview_stage import stage_payload

    remaining = _check_remaining_time(interview)
    minutes = max(0, remaining // 60)
    stage = stage_payload(interview.stage)

    return {
        "ok": True,
        "speak": f"当前处于「{stage['label']}」阶段（第 {stage['index']}/{stage['total']} 步），"
        f"已提问 {asked} 轮，剩余约 {minutes} 分钟。",
        "widget": None,
        "data": {"asked": asked, "remainingSeconds": remaining, "stage": stage},
    }


async def _tool_generate_report(session: Session, ctx: ToolContext, args: dict) -> dict:
    from server.services.interview_service import generate_report

    interview = _get_interview(session, ctx)
    if not interview:
        return {"ok": False, "speak": "面试不存在。", "widget": None, "data": {}}

    report = await generate_report(session, interview)
    try:
        dims = json.loads(report.dimension_scores or "[]")
    except json.JSONDecodeError:
        dims = []

    return {
        "ok": True,
        "speak": f"报告已生成，总分 {report.total_score}。{report.summary[:200]}",
        "widget": {
            "type": "interview_report",
            "id": f"report-{interview.id}",
            "data": {
                "interviewId": interview.id,
                "totalScore": report.total_score,
                "summary": report.summary,
                "dimensionScores": dims,
                "jobFit": report.job_fit,
                "matchScore": report.match_score,
            },
        },
        "data": {"reportId": report.id, "ended": True},
    }


async def _tool_set_emotion(session: Session, ctx: ToolContext, args: dict) -> dict:
    emotion = str(args.get("emotion", "")).strip()
    ka = str(args.get("ka", "")).strip()
    reason = str(args.get("reason", "")).strip()

    if not emotion and not ka:
        return {"ok": False, "speak": "未指定情绪或动作。", "widget": None, "data": {}}

    return {
        "ok": True,
        "speak": f"已切换表情为「{emotion}」" + (f"，动作「{ka}」" if ka else "") + "。",
        "widget": None,
        "data": {"emotion": emotion, "ka": ka, "reason": reason, "act": "emotion"},
    }


async def _tool_play_action(session: Session, ctx: ToolContext, args: dict) -> dict:
    ka = str(args.get("ka", "")).strip()
    if not ka:
        return {"ok": False, "speak": "未指定动作。", "widget": None, "data": {}}

    return {
        "ok": True,
        "speak": f"已执行动作「{ka}」。",
        "widget": None,
        "data": {"ka": ka, "act": "action"},
    }


async def _tool_offer_choices(session: Session, ctx: ToolContext, args: dict) -> dict:
    """下发交互控件（Picker）：候选人点选后由 /command 端点直接执行，不经过 LLM。"""
    title = str(args.get("title") or "").strip()
    options = args.get("options") or []
    widget = build_choices_widget(title, options if isinstance(options, list) else [])
    if not widget:
        return {"ok": False, "speak": "选项无效，请改为直接提问。", "widget": None, "data": {}}

    labels = "、".join(opt["label"] for opt in widget["data"]["options"])
    return {
        "ok": True,
        "speak": f"已向候选人展示可点选项：{labels}。等待候选人点选，不要重复念出选项。",
        "widget": widget,
        "data": {"choices": widget["data"]["options"]},
    }


_DISPATCH: dict[str, Any] = {
    "get_job_description": _tool_get_job_description,
    "analyze_resume": _tool_analyze_resume,
    "match_resume_to_jd": _tool_match_resume_to_jd,
    "retrieve_knowledge": _tool_retrieve_knowledge,
    "pick_algorithm_problem": _tool_pick_algorithm_problem,
    "run_code": _tool_run_code,
    "score_answer": _tool_score_answer,
    "get_interview_progress": _tool_get_interview_progress,
    "generate_report": _tool_generate_report,
    "set_emotion": _tool_set_emotion,
    "play_action": _tool_play_action,
    "offer_choices": _tool_offer_choices,
}


async def _execute_mcp_tool(name: str, args: dict) -> dict:
    """把 `mcp_*` 工具转发到 MCP server（外部可插拔能力，见 docs/MCP接入方案.md）。"""
    try:
        from server.services.mcp_service import call_openai_tool

        result = await call_openai_tool(name, args or {})
    except Exception as e:
        print(f"[Interview Tools] MCP {name} failed: {e}")
        return {
            "ok": False,
            "speak": "外部工具暂不可用，请用你自己的判断继续提问。",
            "widget": None,
            "data": {"source": "mcp"},
        }

    if not result.get("ok"):
        return {
            "ok": False,
            "speak": str(result.get("text") or "外部工具调用失败。"),
            "widget": None,
            "data": {"source": "mcp"},
        }
    return {
        "ok": True,
        "speak": str(result.get("text") or "")[:4000],
        "widget": None,
        "data": {"source": "mcp"},
    }


async def execute_tool(name: str, args: dict, ctx: ToolContext) -> dict:
    """执行工具并返回统一结构。

    任何异常都被收敛为 `ok=False`，避免单个工具失败中断整场面试。
    """
    from server.database import engine

    handler = _DISPATCH.get(name)
    if handler is None:
        if name.startswith("mcp_"):
            return await _execute_mcp_tool(name, args or {})
        return {"ok": False, "speak": f"未知工具：{name}", "widget": None, "data": {}}

    try:
        with Session(engine) as session:
            return await handler(session, ctx, args or {})
    except Exception as e:
        print(f"[Interview Tools] {name} failed: {e}")
        return {
            "ok": False,
            "speak": f"工具 {name} 执行失败，请改用你自己的判断继续提问。",
            "widget": None,
            "data": {},
        }
