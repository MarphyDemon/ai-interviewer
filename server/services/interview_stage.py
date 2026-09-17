"""面试流程状态机：阶段定义、合法转移、持久化与 SSE 广播。

阶段（stage）是面试编排的显式状态，取代过去「只看 LLM 返回 action」的隐式流程：

    opening(开场) → ask(提问) ⇄ followup(追问) → algorithm(算法题) → judge(判题)
                  ↘ closing(收尾) → report(报告) → finished(已结束)

两条链路（文字 JSON 路径 interview_service、语音 brain 路径 interview_brain_service）
共用同一份阶段定义，阶段变化会同时落库（interview.stage）并广播 SSE `stage` 事件。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Session

from server.models import Interview

# ---------- 阶段常量 ----------

STAGE_OPENING = "opening"
STAGE_ASK = "ask"
STAGE_FOLLOWUP = "followup"
STAGE_ALGORITHM = "algorithm"
STAGE_JUDGE = "judge"
STAGE_CLOSING = "closing"
STAGE_REPORT = "report"
STAGE_FINISHED = "finished"

STAGE_ORDER: list[str] = [
    STAGE_OPENING,
    STAGE_ASK,
    STAGE_FOLLOWUP,
    STAGE_ALGORITHM,
    STAGE_JUDGE,
    STAGE_CLOSING,
    STAGE_REPORT,
    STAGE_FINISHED,
]

# 前端步骤条展示用（不含内部终态 finished）
PROGRESS_STAGES: list[str] = [
    STAGE_OPENING,
    STAGE_ASK,
    STAGE_FOLLOWUP,
    STAGE_ALGORITHM,
    STAGE_JUDGE,
    STAGE_CLOSING,
    STAGE_REPORT,
]

STAGE_LABELS: dict[str, dict[str, str]] = {
    STAGE_OPENING: {"zh": "开场", "en": "Opening"},
    STAGE_ASK: {"zh": "提问", "en": "Question"},
    STAGE_FOLLOWUP: {"zh": "追问", "en": "Follow-up"},
    STAGE_ALGORITHM: {"zh": "算法题", "en": "Coding"},
    STAGE_JUDGE: {"zh": "判题", "en": "Review"},
    STAGE_CLOSING: {"zh": "收尾", "en": "Closing"},
    STAGE_REPORT: {"zh": "报告", "en": "Report"},
    STAGE_FINISHED: {"zh": "已结束", "en": "Finished"},
}

# LLM 返回的 action → 阶段
_ACTION_TO_STAGE: dict[str, str] = {
    "ask": STAGE_ASK,
    "followup": STAGE_FOLLOWUP,
    "next_question": STAGE_ASK,
    "algorithm": STAGE_ALGORITHM,
    "end": STAGE_CLOSING,
}

# 合法转移表：防止 LLM 乱跳（例如从收尾跳回开场）
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    STAGE_OPENING: {STAGE_ASK, STAGE_FOLLOWUP, STAGE_ALGORITHM, STAGE_CLOSING, STAGE_REPORT},
    STAGE_ASK: {STAGE_ASK, STAGE_FOLLOWUP, STAGE_ALGORITHM, STAGE_CLOSING, STAGE_REPORT, STAGE_FINISHED},
    STAGE_FOLLOWUP: {STAGE_FOLLOWUP, STAGE_ASK, STAGE_ALGORITHM, STAGE_CLOSING, STAGE_REPORT, STAGE_FINISHED},
    STAGE_ALGORITHM: {STAGE_JUDGE, STAGE_ASK, STAGE_FOLLOWUP, STAGE_CLOSING, STAGE_REPORT, STAGE_FINISHED},
    STAGE_JUDGE: {STAGE_ASK, STAGE_FOLLOWUP, STAGE_ALGORITHM, STAGE_CLOSING, STAGE_REPORT, STAGE_FINISHED},
    STAGE_CLOSING: {STAGE_REPORT, STAGE_FINISHED, STAGE_ASK},
    STAGE_REPORT: {STAGE_FINISHED},
    STAGE_FINISHED: set(),
}

# 注入 system prompt 的阶段指引（让 LLM 的行为与状态机一致）
_STAGE_HINTS: dict[str, str] = {
    STAGE_OPENING: "当前阶段：开场。简短问候后抛出第一个问题；需要候选人做选择时调用 offer_choices。",
    STAGE_ASK: "当前阶段：提问。围绕岗位与简历提出一个新问题，一次只问一个。",
    STAGE_FOLLOWUP: "当前阶段：追问。针对上一轮回答的细节深挖，同一题最多追问 2 次。",
    STAGE_ALGORITHM: "当前阶段：算法题。题目已下发，等待候选人作答；候选人说已提交或要求评测时调用 run_code。",
    STAGE_JUDGE: "当前阶段：判题讲解。结合判题结果说明失败用例与改进方向，然后回到正常提问。",
    STAGE_CLOSING: "当前阶段：收尾。时间或题量已到，礼貌收尾，不要再开启新的大题。",
    STAGE_REPORT: "当前阶段：报告。调用 generate_report 生成报告，再用一两句话说明结果。",
    STAGE_FINISHED: "当前阶段：面试已结束。",
}


# ---------- 查询与转换 ----------


def normalize_stage(stage: Optional[str]) -> str:
    """把空值/未知值归一为合法阶段（兼容老数据）。"""
    if stage and stage in _ALLOWED_TRANSITIONS:
        return stage
    return STAGE_OPENING


def stage_from_action(action: Optional[str]) -> Optional[str]:
    """LLM 返回的 action → 目标阶段；未知 action 返回 None。"""
    if not action:
        return None
    return _ACTION_TO_STAGE.get(str(action).strip())


def can_transition(current: str, target: str) -> bool:
    return target in _ALLOWED_TRANSITIONS.get(normalize_stage(current), set())


def stage_index(stage: str) -> int:
    """阶段在步骤条中的序号（1-based）；finished 视为最后一步。"""
    normalized = normalize_stage(stage)
    if normalized == STAGE_FINISHED:
        return len(PROGRESS_STAGES)
    try:
        return PROGRESS_STAGES.index(normalized) + 1
    except ValueError:
        return 1


def stage_payload(stage: str) -> dict:
    """SSE / 接口统一回传的阶段载荷。"""
    normalized = normalize_stage(stage)
    labels = STAGE_LABELS.get(normalized, {"zh": normalized, "en": normalized})
    return {
        "stage": normalized,
        "index": stage_index(normalized),
        "total": len(PROGRESS_STAGES),
        "label": labels["zh"],
        "labelEn": labels["en"],
    }


def stage_hint(stage: str) -> str:
    """注入 prompt 的阶段指引文本。"""
    return _STAGE_HINTS.get(normalize_stage(stage), "")


# ---------- 状态转移 ----------


def advance_stage(
    session: Session,
    interview: Interview,
    target: Optional[str],
    reason: str = "",
    force: bool = False,
) -> bool:
    """推进面试阶段并广播 SSE 事件。

    - 目标为空或与当前一致时不做任何事（幂等），返回 False
    - 非法转移会记一条日志并忽略（除非 force=True，用于报告/结束等强制收敛）
    """
    if not target:
        return False

    current = normalize_stage(interview.stage)
    if target == current:
        return False

    if not force and not can_transition(current, target):
        print(f"[Interview Stage] illegal transition {current} -> {target} (interview={interview.id})")
        return False

    if target not in _ALLOWED_TRANSITIONS:
        print(f"[Interview Stage] unknown stage {target} (interview={interview.id})")
        return False

    interview.stage = target
    interview.stage_updated_at = datetime.utcnow()
    session.add(interview)
    session.commit()

    payload = stage_payload(target)
    payload["type"] = "stage"
    if reason:
        payload["reason"] = reason

    if interview.id:
        from server.services.interview_event_bus import publish

        publish(interview.id, payload)

    return True


def advance_by_action(session: Session, interview: Interview, action: Optional[str]) -> bool:
    """按 LLM 返回的 action 推进阶段（文字链路便捷入口）。"""
    return advance_stage(session, interview, stage_from_action(action), reason=f"action:{action or ''}")
