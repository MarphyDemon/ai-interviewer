import json
from typing import Optional
from sqlmodel import Session
from server.models import Resume
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
