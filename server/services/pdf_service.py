"""PDF 报告生成服务"""
import io
import json
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# 注册中文字体
import os

_FONT_REGISTERED = False


def _ensure_font():
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    font_paths = [
        ("C:/Windows/Fonts/msyh.ttc", "MSYH"),
        ("C:/Windows/Fonts/simhei.ttf", "SIMHEI"),
        ("C:/Windows/Fonts/simsun.ttc", "SIMSUN"),
    ]
    for path, name in font_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                _FONT_REGISTERED = True
                return
            except Exception:
                continue
    # 没有中文字体也能继续，只是中文会显示为方块
    _FONT_REGISTERED = True


def _get_font_name() -> str:
    """返回可用的中文字体名"""
    for path, name in [
        ("C:/Windows/Fonts/msyh.ttc", "MSYH"),
        ("C:/Windows/Fonts/simhei.ttf", "SIMHEI"),
        ("C:/Windows/Fonts/simsun.ttc", "SIMSUN"),
    ]:
        if os.path.exists(path):
            return name
    return "Helvetica"


def generate_report_pdf(report_data: dict) -> bytes:
    """生成面试报告 PDF"""
    _ensure_font()
    font_name = _get_font_name()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=22,
        alignment=TA_CENTER,
        spaceAfter=20,
    )
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=14,
        spaceBefore=16,
        spaceAfter=8,
        textColor=colors.HexColor("#1a56db"),
    )
    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=10,
        leading=16,
        spaceAfter=6,
    )
    small_style = ParagraphStyle(
        "Small",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#666666"),
    )

    story = []

    # 标题
    story.append(Paragraph("面试点评报告", title_style))
    story.append(Spacer(1, 10))

    # 总分
    total_score = report_data.get("totalScore", 0)
    score_style = ParagraphStyle(
        "Score",
        fontName=font_name,
        fontSize=36,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1a56db"),
        spaceAfter=6,
    )
    label_style = ParagraphStyle(
        "Label",
        fontName=font_name,
        fontSize=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#9ca3af"),
        spaceAfter=20,
    )
    story.append(Paragraph(str(total_score), score_style))
    story.append(Paragraph("总分", label_style))

    # 维度评分
    dimensions = report_data.get("dimensionScores", [])
    if dimensions:
        story.append(Paragraph("维度评分", heading_style))
        table_data = [["维度", "评分"]]
        for dim in dimensions:
            label = dim.get("label", "")
            score = dim.get("score", 0)
            table_data.append([label, str(score)])
        table = Table(table_data, colWidths=[100 * mm, 40 * mm])
        table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a56db")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ])
        )
        story.append(table)
        story.append(Spacer(1, 10))

    # 总结
    summary = report_data.get("summary", "")
    if summary:
        story.append(Paragraph("总结", heading_style))
        story.append(Paragraph(summary, body_style))

    # 岗位匹配度
    job_fit = report_data.get("jobFit", "")
    if job_fit:
        story.append(Paragraph("岗位匹配分析", heading_style))
        story.append(Paragraph(job_fit, body_style))

    # 简历点评
    resume_review = report_data.get("resumeReview")
    if resume_review and isinstance(resume_review, dict):
        story.append(Paragraph("简历评估", heading_style))
        review_data = [
            ["结构评分", str(resume_review.get("structureScore", ""))],
            ["岗位匹配度", f"{resume_review.get('positionMatch', 0)}%"],
        ]
        table = Table(review_data, colWidths=[60 * mm, 80 * mm])
        table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ])
        )
        story.append(table)
        story.append(Spacer(1, 10))

    # 逐题点评
    per_question = report_data.get("perQuestionReviews", [])
    if per_question:
        story.append(PageBreak())
        story.append(Paragraph("逐题点评", heading_style))
        for i, q in enumerate(per_question):
            story.append(Spacer(1, 8))
            story.append(Paragraph(f"<b>Q{i + 1}: {q.get('question', '')}</b>", body_style))
            story.append(Paragraph(f"<b>你的回答:</b> {q.get('answer', '')}", small_style))
            story.append(Paragraph(f"<b>点评:</b> {q.get('review', '')}", body_style))
            story.append(Paragraph(f"<b>参考答案:</b> {q.get('referenceAnswer', '')}", small_style))
            story.append(Paragraph(f"<b>得分: {q.get('score', 0)}</b>", small_style))
            story.append(Spacer(1, 4))

    doc.build(story)
    return buf.getvalue()


def generate_resume_report_pdf(report: dict) -> bytes:
    """生成简历深度评估报告 PDF"""
    _ensure_font()
    font_name = _get_font_name()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ResumeTitle", parent=styles["Title"], fontName=font_name,
        fontSize=22, alignment=TA_CENTER, spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        "ResumeHeading", parent=styles["Heading2"], fontName=font_name,
        fontSize=14, spaceBefore=14, spaceAfter=8,
        textColor=colors.HexColor("#1a56db"),
    )
    body_style = ParagraphStyle(
        "ResumeBody", parent=styles["BodyText"], fontName=font_name,
        fontSize=10, leading=16, spaceAfter=6,
    )
    small_style = ParagraphStyle(
        "ResumeSmall", parent=styles["BodyText"], fontName=font_name,
        fontSize=9, leading=13, textColor=colors.HexColor("#666666"),
    )
    grade_style = ParagraphStyle(
        "Grade", fontName=font_name, fontSize=48,
        alignment=TA_CENTER, textColor=colors.HexColor("#1a56db"), spaceAfter=6,
    )
    label_style = ParagraphStyle(
        "GradeLabel", fontName=font_name, fontSize=12,
        alignment=TA_CENTER, textColor=colors.HexColor("#9ca3af"), spaceAfter=20,
    )

    story = []
    data = report.get("data", {}) or {}

    # 标题
    story.append(Paragraph("简历深度评估报告", title_style))
    position = report.get("position", "")
    if position:
        story.append(Paragraph(f"目标岗位：{position}", label_style))
    story.append(Spacer(1, 6))

    # 综合评级
    grade = data.get("grade", "B")
    story.append(Paragraph(str(grade), grade_style))
    story.append(Paragraph("综合评级（S/A/B/C/D）", label_style))

    # 评分维度表
    score_rows = [
        ["维度", "评分"],
        ["结构完整度", str(data.get("structureScore", 0))],
        ["岗位匹配度", f"{data.get('positionMatch', 0)}%"],
        ["技能覆盖度", str(data.get("skillCoverage", 0))],
        ["项目深度", str(data.get("projectDepth", 0))],
    ]
    story.append(Paragraph("评分维度", heading_style))
    table = Table(score_rows, colWidths=[80 * mm, 40 * mm])
    table.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a56db")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(table)
    story.append(Spacer(1, 10))

    # 亮点
    highlights = data.get("highlights", []) or []
    if highlights:
        story.append(Paragraph("亮点", heading_style))
        for h in highlights:
            story.append(Paragraph(f"• {h}", body_style))

    # 不足
    weaknesses = data.get("weaknesses", []) or []
    if weaknesses:
        story.append(Paragraph("不足", heading_style))
        for w in weaknesses:
            story.append(Paragraph(f"• {w}", body_style))

    # 改进建议
    improvements = data.get("improvements", []) or []
    if improvements:
        story.append(Paragraph("改进建议", heading_style))
        for imp in improvements:
            section = imp.get("section", "") if isinstance(imp, dict) else ""
            suggestion = imp.get("suggestion", "") if isinstance(imp, dict) else str(imp)
            story.append(Paragraph(f"<b>{section}</b>：{suggestion}", body_style))

    # 可投递岗位
    recommended = data.get("recommendedPositions", []) or []
    if recommended:
        story.append(Paragraph("可投递岗位建议", heading_style))
        story.append(Paragraph("、".join(recommended), body_style))

    doc.build(story)
    return buf.getvalue()
