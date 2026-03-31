"""Token 用量：端点类型判定与无 API usage 时的粗略估算（中英混合按字符量近似）。"""

from __future__ import annotations

import json
from typing import Any


def infer_endpoint_kind(api_base: str) -> str:
    """根据 Base URL 区分本地（Ollama 等）与在线服务。"""
    u = (api_base or "").lower()
    for marker in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        if marker in u:
            return "local"
    return "remote"


def estimate_tokens_from_text(text: str) -> int:
    """粗略 token 数：偏 CJK 场景略多计。"""
    if not text:
        return 0
    return max(1, (len(text) + 1) // 2)


def estimate_embed_usage_for_texts(texts: list[str]) -> tuple[int, int]:
    """本地 embedding 无 API 时：prompt/total 均用输入字符估算之和。"""
    n = sum(estimate_tokens_from_text(t) for t in texts)
    return n, n


def estimate_chat_prompt_tokens(messages: list[dict[str, str]]) -> int:
    try:
        blob = json.dumps(messages, ensure_ascii=False)
    except (TypeError, ValueError):
        blob = "".join(m.get("content", "") for m in messages)
    return estimate_tokens_from_text(blob)


def estimate_chat_completion_tokens(assistant_text: str) -> int:
    return estimate_tokens_from_text(assistant_text)


def parse_openai_usage(u: dict[str, Any] | None) -> tuple[int | None, int | None, int | None]:
    """从 OpenAI 风格 usage 字典解析 prompt / completion / total。"""
    if not u or not isinstance(u, dict):
        return None, None, None
    pt = u.get("prompt_tokens")
    ct = u.get("completion_tokens")
    tt = u.get("total_tokens")
    try:
        pti = int(pt) if pt is not None else None
    except (TypeError, ValueError):
        pti = None
    try:
        cti = int(ct) if ct is not None else None
    except (TypeError, ValueError):
        cti = None
    try:
        tti = int(tt) if tt is not None else None
    except (TypeError, ValueError):
        tti = None
    return pti, cti, tti


def parse_embedding_usage(u: dict[str, Any] | None) -> tuple[int | None, int | None]:
    if not u or not isinstance(u, dict):
        return None, None
    pt = u.get("prompt_tokens")
    tt = u.get("total_tokens")
    try:
        pti = int(pt) if pt is not None else None
    except (TypeError, ValueError):
        pti = None
    try:
        tti = int(tt) if tt is not None else None
    except (TypeError, ValueError):
        tti = None
    if pti is not None and tti is None:
        tti = pti
    return pti, tti
