"""按扩展名选择解析器：PDF 用 pypdf 逐页抽文本，其余按 UTF-8 读文本（非法字节忽略）。"""

from pathlib import Path


def extract_text_from_file(path: str) -> str:
    p = Path(path)
    suf = p.suffix.lower()
    if suf == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(path)
        parts: list[str] = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)
    return p.read_text(encoding="utf-8", errors="ignore")
