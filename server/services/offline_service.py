"""离线规则模式（OFFLINE_MODE=true）

用途：在没有网络、没有 LLM / Embedding 凭证的环境下，让
「出题 → 答题 → 判题 → 报告」这条主流程依然可以完整跑通，便于评审与演示。

**它不是大模型**，能力边界必须说清楚：
- 出题：来自内置题库（按岗位方向选取），追问/换题/结束由规则决定
- 点评与评分：来自可解释的统计规则（回答长度、技术关键词命中、判题结果），不是语义理解
- 知识库检索：退化为关键词匹配，不做向量化（ChromaDB 不参与）
- 具身播报：仍然依赖魔珐云端，未配置凭证时走前端 Lottie + 浏览器语音降级

启用方式：环境变量 OFFLINE_MODE=true（见 README「方式 B」）。
"""

import json
import re
from typing import AsyncGenerator, Optional

from sqlmodel import Session, select

from server.config import settings

# ---------- 内置题库 ----------
# 每项：q=问题，ref=参考答案，tags=知识点标签
QUESTION_BANK: dict[str, list[dict]] = {
    "前端": [
        {
            "q": "请介绍一下你在前端项目里负责过的模块，以及你具体做了什么。",
            "ref": "建议按「背景 → 我的职责 → 技术选型 → 结果与数据」四段式回答，突出个人贡献而非团队产出。",
            "tags": ["项目经验", "表达结构"],
        },
        {
            "q": "说说浏览器从输入 URL 到页面渲染完成，中间经历了哪些关键阶段？",
            "ref": "DNS 解析 → TCP/TLS 连接 → 发送 HTTP 请求 → 服务端响应 → 解析 HTML 构建 DOM → CSSOM → 渲染树 → 布局 → 绘制 → 合成；还涉及阻塞资源、重排重绘等。",
            "tags": ["浏览器原理", "性能"],
        },
        {
            "q": "Vue 3 的响应式系统相比 Vue 2 有什么变化？实际项目里你怎么避免不必要的更新？",
            "ref": "Vue 3 用 Proxy 替代 defineProperty，支持数组与新增属性；可用 shallowRef、computed 缓存、v-memo、虚拟列表等手段减少渲染。",
            "tags": ["框架原理", "性能优化"],
        },
        {
            "q": "前端如何做请求层的错误处理与弱网体验？请结合你做过的项目说明。",
            "ref": "统一拦截器、超时与重试、乐观更新与回滚、骨架屏/占位、离线缓存、错误上报与降级提示。",
            "tags": ["工程化", "稳定性"],
        },
        {
            "q": "如果要你优化一个首屏 5 秒的管理后台，你会按什么顺序排查和优化？",
            "ref": "先量化（Lighthouse/Performance 面板）→ 查网络瀑布（分包、体积、CDN、HTTP 缓存）→ 查主线程（长任务、重复渲染）→ 按收益排序逐项改造。",
            "tags": ["性能优化", "方法论"],
        },
    ],
    "后端": [
        {
            "q": "请挑一个你负责过的接口，讲讲它的 QPS、瓶颈在哪、你怎么优化的。",
            "ref": "从数据量、调用链、慢查询、锁竞争、缓存命中率等角度说明，并给出优化前后的量化对比。",
            "tags": ["项目经验", "性能"],
        },
        {
            "q": "数据库索引失效的常见场景有哪些？你如何定位一条慢 SQL？",
            "ref": "隐式类型转换、函数包裹列、前导模糊匹配、不满足最左前缀、区分度低等；先用慢查询日志/EXPLAIN 定位，再看执行计划与扫描行数。",
            "tags": ["数据库", "索引"],
        },
        {
            "q": "缓存与数据库如何保持一致？请说明你采用的方案和它的失效边界。",
            "ref": "常见 Cache Aside（先更新库再删缓存）、延迟双删、订阅 binlog 等；要说明不一致窗口与兜底（过期时间、重试、对账）。",
            "tags": ["缓存", "一致性"],
        },
        {
            "q": "线上接口突然 500 增多，你的排查步骤是什么？",
            "ref": "先看监控与错误率曲线、再查日志与调用链、确认是否发布/流量/依赖变更，必要时先降级止损再定位根因。",
            "tags": ["故障排查", "稳定性"],
        },
        {
            "q": "你们服务如何做并发控制？谈谈你对锁和幂等的实践。",
            "ref": "乐观锁/悲观锁、分布式锁的选型与风险、唯一索引兜底、幂等键设计、重试与超时策略。",
            "tags": ["并发", "幂等"],
        },
    ],
    "算法": [
        {
            "q": "讲一个你印象最深的算法/数据结构使用场景，为什么选它？",
            "ref": "说明问题规模、约束与候选方案对比（复杂度、常数、可维护性），而不是只背复杂度。",
            "tags": ["算法思维"],
        },
        {
            "q": "哈希表和平衡树的适用场景分别是什么？",
            "ref": "哈希表平均 O(1) 但不支持范围查询与有序遍历；平衡树 O(log n) 支持有序与范围操作，内存开销更大。",
            "tags": ["数据结构"],
        },
        {
            "q": "什么情况下动态规划比贪心更合适？举例说明。",
            "ref": "当局部最优无法推出全局最优（无最优子结构的贪心选择性质不成立）时用 DP，如零钱兑换、编辑距离。",
            "tags": ["动态规划"],
        },
        {
            "q": "如何判断一段代码的时间复杂度？请以你写过的代码为例。",
            "ref": "找循环嵌套层数、递归深度与每层工作量、均摊分析；注意隐式的 O(n) 操作（如切片、字符串拼接）。",
            "tags": ["复杂度分析"],
        },
        {
            "q": "海量数据去重、Top K 这类问题你会怎么设计？",
            "ref": "分治+哈希分片、Bitmap、布隆过滤器、小顶堆维护 Top K，必要时结合外部排序与流式处理。",
            "tags": ["系统设计", "大数据"],
        },
    ],
    "数据": [
        {
            "q": "请介绍一个你做过数据分析项目，指标是怎么定义的？",
            "ref": "说明业务目标 → 指标口径 → 数据来源与清洗 → 结论与动作，强调可复现与口径一致性。",
            "tags": ["项目经验", "指标体系"],
        },
        {
            "q": "数据倾斜是怎么产生的？你会如何排查和处理？",
            "ref": "key 分布不均、join 放大、空值集中等；可用加盐打散、map join、预处理聚合、调整并行度解决。",
            "tags": ["数据工程"],
        },
        {
            "q": "如何评估一个离线指标的可靠性？",
            "ref": "样本量与置信区间、口径变更影响、数据链路监控与数据质量校验（唯一性、完整性、及时性）。",
            "tags": ["数据质量"],
        },
        {
            "q": "如果 A/B 实验结论与直觉不符，你会怎么处理？",
            "ref": "先验证分流与埋点正确性、样本量是否足够、是否存在新奇效应或 SRM，再做分群与稳健性检验。",
            "tags": ["实验设计"],
        },
    ],
    "通用": [
        {
            "q": "请用两分钟做一个自我介绍，重点讲你和这个岗位相关的经历。",
            "ref": "结构：我是谁 → 我做过的与岗位最相关的两件事 → 为什么匹配这个岗位。控制在两分钟，给面试官留提问抓手。",
            "tags": ["自我介绍"],
        },
        {
            "q": "讲一个你推动过的最有挑战的事情，你具体怎么做的？",
            "ref": "用 STAR 结构：情境、任务、你的行动（重点）、可量化结果，并说明如果重来会怎么改进。",
            "tags": ["行为面试", "STAR"],
        },
        {
            "q": "你和同事产生过技术分歧吗？最后怎么达成一致的？",
            "ref": "展示沟通与证据驱动的决策方式：把分歧收敛到可验证的假设上（压测、原型、灰度），而不是靠职级。",
            "tags": ["协作", "沟通"],
        },
        {
            "q": "你最近在学什么？为什么学它？",
            "ref": "体现自驱与方向感：学习动因 → 学习方式 → 已落地的产出，而不是罗列课程名。",
            "tags": ["成长性"],
        },
        {
            "q": "你未来一到两年的职业规划是什么？",
            "ref": "与岗位成长路径对齐，说明想补的能力短板和希望承担的职责，避免空泛的目标。",
            "tags": ["职业规划"],
        },
    ],
}

# 用于生成「参考答案」匹配的通用技术关键词（评分维度参考）
TECH_KEYWORDS = [
    "性能", "优化", "缓存", "索引", "并发", "一致性", "测试", "监控", "部署",
    "重构", "架构", "数据", "复杂度", "接口", "设计", "排查", "指标", "方案",
]

_INSTRUCTION_MARKERS = ("请开始面试", "Start the interview")


def enabled() -> bool:
    """离线规则模式是否启用。"""
    return bool(settings.offline_mode)


# ---------- 意图识别（基于调用方 prompt 的特征串） ----------


def _detect_intent(text: str) -> str:
    if '"action"' in text and "next_question" in text:
        return "interview_question"
    if '"totalScore"' in text:
        return "interview_report"
    if '"recommendedPositions"' in text:
        return "resume_report"
    if '"score"' in text and "verdict" in text:
        return "score_answer"
    if '"matchScore"' in text and "matchBreakdown" in text:
        return "match_jd"
    if '"structureScore"' in text:
        return "resume_light"
    if "提取元信息" in text:
        return "doc_metadata"
    return "chat"


# ---------- 出题 ----------


def _position_bank(position: str) -> list[dict]:
    for key in QUESTION_BANK:
        if key != "通用" and key in (position or ""):
            return QUESTION_BANK[key] + QUESTION_BANK["通用"]
    return QUESTION_BANK["通用"]


def _extract_context(prompt: str) -> dict:
    """从调用方 prompt 中抽取岗位 / 难度 / 候选人回答。"""
    position, difficulty = "", ""
    zh = re.search(r"正在面试(.+?)方向的(.+?)级别候选人", prompt)
    en = re.search(r"conducting a (.+?)-level interview for a (.+?) position", prompt)
    if zh:
        position, difficulty = zh.group(1), zh.group(2)
    elif en:
        difficulty, position = en.group(1), en.group(2)

    answers = [
        m.group(1).strip()
        for m in re.finditer(r"^Candidate:\s*(.+)$", prompt, re.MULTILINE)
    ]
    interviewers = re.findall(r"^Interviewer:\s*(.+)$", prompt, re.MULTILINE)
    return {
        "position": position or "通用",
        "difficulty": difficulty or "中等",
        "answers": answers,
        "questions": interviewers,
    }


def _candidate_answers(messages: list[dict]) -> list[str]:
    """取出候选人的真实回答。

    注意：调用方（process_answer）会先把本轮回答落库、再把它附到 messages 末尾，
    因此最后一轮回答在 messages 中会出现两次 —— 这里只去掉末尾这一份重复，
    不影响候选人真的连续给出相同回答的情况。
    """
    answers = [
        m.get("content", "")
        for m in messages
        if m.get("role") == "user"
        and not any(mark in m.get("content", "") for mark in _INSTRUCTION_MARKERS)
    ]
    if len(answers) >= 2 and answers[-1] == answers[-2]:
        answers.pop()
    return answers


def _answer_question(messages: list[dict]) -> dict:
    """规则驱动的出题：首问 → 追问 → 换题 → 算法题 → 结束。"""
    joined = "\n".join(m.get("content", "") for m in messages)
    ctx = _extract_context(joined)
    bank = _position_bank(ctx["position"])

    answers = _candidate_answers(messages)
    turns = len(answers)
    last = answers[-1] if answers else ""

    if turns == 0:
        return _q("ask", bank[0], ctx)

    if turns >= len(bank):
        return {
            "action": "end",
            "content": f"今天的问题基本聊完了，感谢你的时间。本次面试共 {turns} 轮问答，稍后为你生成评估报告。",
            "reasoning": "题库已问完，按规则结束面试",
        }

    # 回答明显过短 → 追问同一题（最多连续 2 次）
    if len(last.strip()) < 40:
        idx = min(turns - 1, len(bank) - 1)
        return {
            "action": "followup",
            "content": (
                f"你的回答还比较概括。能不能就「{bank[idx]['q']}」再具体一点——"
                "比如你实际做了什么、遇到什么问题、最后的结果是什么？"
            ),
            "reasoning": f"上一轮回答仅 {len(last.strip())} 字，证据不足，触发追问",
        }

    # 中段安排一道算法题
    if turns % 3 == 2:
        return {
            "action": "algorithm",
            "content": "接下来是一道编码题，请你在编辑器里完成，写完可以直接提交判题。",
            "reasoning": "进入面试中段，按规则安排编码题",
        }

    return _q("next_question", bank[turns], ctx)


def _q(action: str, item: dict, ctx: dict) -> dict:
    return {
        "action": action,
        "content": item["q"],
        "reasoning": f"离线题库出题（{ctx['position']} / {ctx['difficulty']} / {','.join(item['tags'])}）",
    }


# ---------- 报告 ----------


def _score_from_answers(answers: list[str]) -> tuple[int, int, int, int]:
    """基于可解释规则的评分：完整度 / 表达 / 专业度 / 综合。"""
    if not answers:
        return 40, 40, 40, 40
    avg_len = sum(len(a) for a in answers) / len(answers)
    completeness = min(95, 45 + int(min(avg_len, 400) / 400 * 50))
    hits = sum(1 for a in answers for k in TECH_KEYWORDS if k in a)
    depth = min(95, 45 + min(hits, 20) * 2)
    expression = min(95, 50 + (10 if avg_len >= 80 else 0) + min(len(answers), 5) * 5)
    total = int(completeness * 0.35 + depth * 0.4 + expression * 0.25)
    return completeness, expression, depth, total


def _answer_report(prompt: str) -> dict:
    ctx = _extract_context(prompt)
    answers = ctx["answers"]
    completeness, expression, depth, total = _score_from_answers(answers)
    # 报告阶段拿不到岗位（prompt 里只有对话记录），因此跨全部题库匹配参考答案
    by_question = {item["q"]: item for items in QUESTION_BANK.values() for item in items}

    reviews = []
    for i, ans in enumerate(answers):
        q = ctx["questions"][i] if i < len(ctx["questions"]) else f"第 {i + 1} 题"
        ref = by_question.get(q, {}).get("ref", "考察点：结论明确、有具体证据、能讲清取舍。")
        scaled = min(95, 45 + int(min(len(ans), 400) / 400 * 50))
        reviews.append(
            {
                "question": q,
                "answer": ans,  # 报告中展示候选人原始回答，便于对照
                "review": (
                    f"回答长度 {len(ans)} 字，"
                    + ("信息量较充分，建议补充量化结果与取舍依据。" if len(ans) >= 120
                       else "偏简略，建议用「背景-行动-结果」结构展开。")
                ),
                "referenceAnswer": ref,
                "score": scaled,
            }
        )

    has_jd = "Job Description (if available):" in prompt and "N/A" not in prompt.split("Job Description (if available):")[-1][:20]
    data = {
        "totalScore": total,
        "dimensionScores": [
            {"label": "Technical Knowledge", "score": depth},
            {"label": "Communication", "score": expression},
            {"label": "Job Fit", "score": completeness},
            {"label": "Problem Solving", "score": depth},
            {"label": "Technical Depth", "score": depth},
        ],
        "summary": (
            f"离线规则评估：本次共 {len(answers)} 轮问答，平均回答长度 "
            f"{int(sum(len(a) for a in answers) / len(answers)) if answers else 0} 字。"
            "评分由回答完整度、技术关键词覆盖与表达结构三项规则计算得出，"
            "不代表语义级评价，仅供流程演示。"
        ),
        "perQuestionReviews": reviews,
        "resumeReview": {
            "structureScore": 70,
            "positionMatch": completeness,
            "highlights": ["简历已成功解析并参与提问"],
            "weaknesses": ["建议补齐量化结果与项目难点"],
        },
        "jobFit": "离线模式未做语义级人岗匹配，建议配置 LLM 后重新生成。",
    }
    if has_jd:
        data["matchScore"] = completeness
        data["matchBreakdown"] = [
            {"requirement": "（离线模式）未解析 JD 具体条目", "status": "partial", "evidence": "需配置 LLM 后生成逐条对照"}
        ]
    return data


def _answer_score(prompt: str) -> dict:
    answer = ""
    m = re.search(r"候选人回答：(.+)$", prompt, re.DOTALL)
    if m:
        answer = m.group(1).strip()
    length = len(answer)
    hits = [k for k in TECH_KEYWORDS if k in answer]
    score = min(95, 45 + int(min(length, 400) / 400 * 40) + min(len(hits), 5) * 2)
    return {
        "score": score,
        "verdict": "回答完整度尚可" if length >= 120 else "回答偏简略，建议展开细节",
        "strengths": (["提到了 " + "、".join(hits[:3])] if hits else ["结构清晰"]),
        "gaps": (["缺少量化结果"] if length < 120 else ["可补充方案取舍依据"]),
    }


def _answer_match_jd(prompt: str) -> dict:
    jd = ""
    resume = ""
    m = re.search(r"岗位 JD：(.+?)(?:\n候选人简历：|$)", prompt, re.DOTALL)
    if m:
        jd = m.group(1)
    m = re.search(r"候选人简历：(.+)$", prompt, re.DOTALL)
    if m:
        resume = m.group(1)

    terms = [t for t in re.findall(r"[A-Za-z][A-Za-z0-9+#.]{2,}|[\u4e00-\u9fa5]{2,4}", jd)][:40]
    matched = [t for t in terms if t in resume]
    score = int(60 + 35 * (len(matched) / len(terms))) if terms else 60
    return {
        "matchScore": min(score, 95),
        "matchBreakdown": [
            {"requirement": t, "status": "met" if t in resume else "gap", "evidence": "离线关键词比对"}
            for t in terms[:8]
        ],
        "jobFit": (
            f"离线关键词匹配：JD 关键词 {len(terms)} 个，简历命中 {len(matched)} 个。"
            "结论仅为关键词覆盖度，配置 LLM 后可获得语义级评估。"
        ),
    }


_RESUME_SECTIONS = ("项目", "经历", "技能", "教育", "实习", "工作", "负责", "开源")


def _answer_resume(prompt: str, deep: bool) -> dict:
    resume = prompt.split("简历内容：")[-1]
    hits = [s for s in _RESUME_SECTIONS if s in resume]
    structure = min(95, 45 + len(hits) * 8)
    length = len(resume)
    match = min(95, 50 + (10 if length > 800 else 0) + len(hits) * 4)
    common = {
        "structureScore": structure,
        "positionMatch": match,
        "highlights": [f"简历包含「{s}」相关信息" for s in hits[:4]] or ["简历文本已解析"],
        "weaknesses": (
            ["缺少量化数据（如 QPS、耗时、提升比例）"] if not re.search(r"\d+\s*[%倍]|\d+\s*(ms|s|qps)", resume, re.I) else []
        )
        + ([] if "项目" in resume else ["建议补充项目经历段落"]),
    }
    if not deep:
        return common
    return {
        "grade": "B" if match >= 70 else "C",
        "skillCoverage": match,
        "projectDepth": min(95, 45 + (25 if "项目" in resume else 0) + (15 if re.search(r"\d", resume) else 0)),
        "improvements": [
            {"section": "项目经历", "suggestion": "按「背景-职责-技术方案-量化结果」重写，突出个人贡献。"},
            {"section": "技能", "suggestion": "按岗位 JD 的技术栈排序，删掉无关技能。"},
        ],
        "recommendedPositions": ["（离线模式）需配置 LLM 后生成"],
        **common,
    }


def _answer_doc_metadata(prompt: str) -> dict:
    body = prompt.split("文档内容（前2000字）：")[-1]
    first_line = next((ln.strip("# ").strip() for ln in body.splitlines() if ln.strip()), "未命名题目")
    positions = [p for p in ("前端", "后端", "算法", "数据", "运维", "测试") if p in body]
    level = "高级" if "高级" in body else ("初级" if "初级" in body else "中级")
    return {
        "title": first_line[:30] or "未命名题目",
        "position": positions[0] if positions else "通用",
        "difficulty": level,
        "tags": positions[:2] + [level],
    }


# ---------- 通用文本（学习导师 / 代码助手） ----------


def _answer_text(messages: list[dict]) -> str:
    system = "\n".join(m.get("content", "") for m in messages if m.get("role") == "system")
    user = next(
        (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
        "",
    )
    knowledge = ""
    marker = "知识库参考（可能相关，请自行判断相关性）："
    if marker in system:
        knowledge = system.split(marker, 1)[1].strip()

    head = f"【离线规则模式】已收到你的问题：{user[:60]}"
    if knowledge:
        snippet = knowledge[:600]
        return (
            f"{head}\n\n以下是知识库中与该问题相关的原文片段（离线模式为关键词匹配，未做语义理解）：\n\n"
            f"{snippet}\n\n"
            "如需基于大模型的完整回答，请配置 LLM_API_KEY（云端）或使用本地大模型模式（见 README）。"
        )
    return (
        f"{head}\n\n当前为离线规则模式，未接入大模型，无法生成自由问答内容。\n"
        "可选方案：\n"
        "1. 配置 LLM_API_KEY / EMBEDDING_API_KEY（云端模型）\n"
        "2. 使用本地大模型模式（Ollama，无需任何 Key）\n"
        "3. 在「知识库」中导入题目文档后重试（离线模式会返回关键词命中的原文片段）"
    )


# ---------- 对外接口 ----------


def answer(messages: list[dict], json_mode: bool = False) -> str:
    """离线模式下替代 `llm_chat` 的规则应答。"""
    joined = "\n".join(m.get("content", "") for m in messages)
    intent = _detect_intent(joined)

    if intent == "interview_question":
        return json.dumps(_answer_question(messages), ensure_ascii=False)
    if intent == "interview_report":
        return json.dumps(_answer_report(joined), ensure_ascii=False)
    if intent == "score_answer":
        return json.dumps(_answer_score(joined), ensure_ascii=False)
    if intent == "match_jd":
        return json.dumps(_answer_match_jd(joined), ensure_ascii=False)
    if intent == "resume_report":
        return json.dumps(_answer_resume(joined, deep=True), ensure_ascii=False)
    if intent == "resume_light":
        return json.dumps(_answer_resume(joined, deep=False), ensure_ascii=False)
    if intent == "doc_metadata":
        return json.dumps(_answer_doc_metadata(joined), ensure_ascii=False)
    if json_mode:
        # 未识别意图的 JSON 调用返回空对象，由调用方的兜底逻辑处理
        return "{}"
    return _answer_text(messages)


async def stream(messages: list[dict]) -> AsyncGenerator[str, None]:
    """离线模式下替代 `llm_chat_stream`：把规则文本按片段吐出，保持前端流式体验。"""
    text = answer(messages, json_mode=False)
    step = 24
    for i in range(0, len(text), step):
        yield text[i : i + step]


# ---------- 知识库关键词检索 ----------


def keyword_search(
    session: Session,
    query: str,
    top_k: int = 5,
    position: Optional[str] = None,
    doc_ids: Optional[set[int]] = None,
) -> list[str]:
    """离线检索：对 KnowledgeDoc 正文做关键词打分，替代向量检索。

    doc_ids 传入时只在这些文档内检索——面试链路据此做归属过滤，
    避免私有文档或他人组织的知识被检索到。
    """
    from server.models import KnowledgeDoc

    terms = re.findall(r"[A-Za-z][A-Za-z0-9+#.]{2,}|[\u4e00-\u9fa5]{2,}", query or "")
    if not terms:
        return []

    allowed_ids = list(doc_ids) if doc_ids is not None else None
    if allowed_ids is not None and not allowed_ids:
        return []

    stmt = select(KnowledgeDoc)
    if allowed_ids is not None:
        stmt = stmt.where(KnowledgeDoc.id.in_(allowed_ids))
    if position:
        stmt = stmt.where(KnowledgeDoc.position == position)
    docs = session.exec(stmt).all()
    if not docs and position:
        # 放宽岗位过滤重试，但归属约束必须保留
        fallback = select(KnowledgeDoc)
        if allowed_ids is not None:
            fallback = fallback.where(KnowledgeDoc.id.in_(allowed_ids))
        docs = session.exec(fallback).all()

    scored: list[tuple[int, str]] = []
    for doc in docs:
        content = doc.content or ""
        score = sum(content.count(t) for t in terms)
        if score > 0:
            scored.append((score, content[:800]))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]
