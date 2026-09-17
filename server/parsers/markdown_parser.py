import frontmatter
from typing import List, Dict, Tuple


def parse_markdown(content: str) -> Tuple[Dict, str]:
    post = frontmatter.loads(content)
    metadata = dict(post.metadata)
    body = post.content
    return metadata, body


def chunk_markdown(body: str, max_chunk_size: int = 500) -> List[Dict]:
    lines = body.split("\n")
    chunks: List[Dict] = []
    current_section = ""
    current_title = ""
    current_level = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if current_section.strip():
                for chunk in _split_long_text(current_section.strip(), max_chunk_size):
                    chunks.append({
                        "title": current_title,
                        "level": current_level,
                        "content": chunk,
                    })
            current_title = stripped.lstrip("#").strip()
            current_level = len(stripped) - len(stripped.lstrip("#"))
            current_section = stripped + "\n"
        else:
            current_section += line + "\n"

    if current_section.strip():
        for chunk in _split_long_text(current_section.strip(), max_chunk_size):
            chunks.append({
                "title": current_title,
                "level": current_level,
                "content": chunk,
            })

    return chunks


def _split_long_text(text: str, max_size: int) -> List[str]:
    if len(text) <= max_size:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current = ""

    for para in paragraphs:
        # 单个段落超长，按行拆分
        if len(para) > max_size:
            if current.strip():
                chunks.append(current.strip())
                current = ""
            lines = para.split("\n")
            for line in lines:
                if len(current) + len(line) + 1 > max_size and current:
                    chunks.append(current.strip())
                    current = line
                else:
                    current = current + "\n" + line if current else line
        elif len(current) + len(para) + 2 > max_size and current:
            chunks.append(current.strip())
            current = para
        else:
            current = current + "\n\n" + para if current else para

    if current.strip():
        chunks.append(current.strip())

    return chunks
