"""LlamaIndex LLM：OpenAI 兼容（与对话模型一致）。"""

from __future__ import annotations

from llama_index.llms.openai import OpenAI

from app.services.model_resolver import ResolvedOpenAICompat
from app.services.openai_compat import _openai_v1_base


def build_llama_llm(cfg: ResolvedOpenAICompat) -> OpenAI:
    extra = cfg.extra_headers or {}
    default_headers = {str(k): str(v) for k, v in extra.items()} if extra else None
    return OpenAI(
        model=cfg.model_id,
        api_key=cfg.api_key,
        api_base=_openai_v1_base(cfg.api_base),
        default_headers=default_headers,
    )
