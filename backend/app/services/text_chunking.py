"""滑动窗口分块：`overlap` 让跨边界的句子在相邻块中重复出现，减轻切断上下文的问题。"""


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        end = min(i + chunk_size, n)
        piece = text[i:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        i += max(chunk_size - overlap, 1)
    return chunks
