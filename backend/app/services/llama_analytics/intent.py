"""是否值得走业务库问答（减轻每条消息开销）。"""

from __future__ import annotations

from app.core.config import Settings


def should_run_llama_analytics(user_text: str, settings: Settings) -> bool:
    if not settings.llamaindex_enabled:
        return False
    t = (user_text or "").strip()
    if not t:
        return False
    keywords = [k.strip() for k in settings.llamaindex_intent_keywords.split(",") if k.strip()]
    if not keywords:
        return False
    return any(k in t for k in keywords)
