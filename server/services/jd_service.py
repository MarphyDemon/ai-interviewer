from server.parsers.pdf_parser import extract_text_from_pdf
from server.parsers.docx_parser import extract_text_from_docx


def parse_jd_file(file_path: str) -> str:
    """解析 JD 文件，支持 pdf / docx / md / txt，返回纯文本。"""
    lower = file_path.lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf(file_path)
    if lower.endswith(".docx"):
        return extract_text_from_docx(file_path)
    if lower.endswith(".md") or lower.endswith(".markdown"):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    if lower.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""
