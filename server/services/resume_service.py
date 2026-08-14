import json
from typing import Optional
from sqlmodel import Session, select
from server.models import Resume, ResumeReport
from server.parsers.pdf_parser import extract_text_from_pdf
from server.parsers.docx_parser import extract_text_from_docx
from server.services.llm_service import llm_chat


def parse_resume_file(file_path: str) -> str:
    if file_path.endswith(".pdf"):
        return extract_text_from_pdf(file_path)
    elif file_path.endswith(".docx"):
        return extract_text_from_docx(file_path)
    return ""


async def analyze_resume(parsed_text: str, position: str) -> dict:
    prompt = f"""请分析以下简历，给出轻量评估。输出 JSON 格式：
{{"structureScore": 0-100的整数, "positionMatch": 0-100的整数, "highlights": ["亮点1", ...], "weaknesses": ["不足1", ...]}}

目标岗位：{position}

简历内容：
{parsed_text[:3000]}"""

    result = await llm_chat([
        {"role": "system", "content": "你是简历分析专家，请严格按JSON格式输出。"},
        {"role": "user", "content": prompt},
    ])

    try:
        start = result.find("{")
        end = result.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(result[start:end])
    except json.JSONDecodeError:
        pass

    return {
        "structureScore": 0,
        "positionMatch": 0,
        "highlights": [],
        "weaknesses": ["分析失败"],
    }


async def generate_resume_report(parsed_text: str, position: str) -> dict:
    """生成简历深度评估报告（8 项维度）"""
    prompt = f"""你是资深技术招聘专家。请对以下简历进行深度评估，目标岗位为「{position}」。

输出严格 JSON 格式（不要 markdown 代码块）：
{{
  "grade": "S/A/B/C/D 之一（S=优秀，D=不合格）",
  "structureScore": 0-100整数（结构完整度）,
  "positionMatch": 0-100整数（岗位匹配度）,
  "skillCoverage": 0-100整数（技能覆盖度，对照目标岗位要求）,
  "projectDepth": 0-100整数（项目深度与技术含量）,
  "highlights": ["亮点1", "亮点2", ...],
  "weaknesses": ["不足1", "不足2", ...],
  "improvements": [
    {{"section": "工作经历", "suggestion": "具体改进建议"}},
    {{"section": "技能", "suggestion": "具体改进建议"}}
  ],
  "recommendedPositions": ["该简历可投递的其他岗位1", "岗位2"]
}}

简历内容：
{parsed_text[:5000]}"""

    result = await llm_chat([
        {"role": "system", "content": "你是资深技术招聘专家，请严格按JSON格式输出，不要包含任何额外文字。"},
        {"role": "user", "content": prompt},
    ])

    try:
        start = result.find("{")
        end = result.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(result[start:end])
            # 字段兜底
            data.setdefault("grade", "B")
            for k in ("structureScore", "positionMatch", "skillCoverage", "projectDepth"):
                data.setdefault(k, 0)
            data.setdefault("highlights", [])
            data.setdefault("weaknesses", [])
            data.setdefault("improvements", [])
            data.setdefault("recommendedPositions", [])
            return data
    except json.JSONDecodeError:
        pass

    return {
        "grade": "B",
        "structureScore": 0,
        "positionMatch": 0,
        "skillCoverage": 0,
        "projectDepth": 0,
        "highlights": [],
        "weaknesses": ["分析失败，请稍后重试"],
        "improvements": [],
        "recommendedPositions": [],
    }


def get_resume_report(session: Session, resume_id: int, position: str) -> Optional[ResumeReport]:
    """按 resume_id + position 查询已有报告（同简历对同岗位仅保留最新一份）"""
    return session.exec(
        select(ResumeReport)
        .where(ResumeReport.resume_id == resume_id)
        .where(ResumeReport.position == position)
        .order_by(ResumeReport.created_at.desc())
    ).first()
