"""LlamaIndex 使用的 Embedding：远程 OpenAI 兼容或本地 fastembed。"""

from __future__ import annotations

import asyncio

from llama_index.core.embeddings import BaseEmbedding
from llama_index.embeddings.openai import OpenAIEmbedding

from app.core.config import Settings
from app.services.local_embed import embed_texts_local_sync
from app.services.model_resolver import ResolvedOpenAICompat
from app.services.openai_compat import _openai_v1_base


def _openai_embed_model(cfg: ResolvedOpenAICompat) -> OpenAIEmbedding:
    return OpenAIEmbedding(
        model=cfg.model_id,
        api_key=cfg.api_key,
        api_base=_openai_v1_base(cfg.api_base),
    )


class LocalFastembedEmbedding(BaseEmbedding):
    """与对话侧一致的本地 fastembed，同步推理。"""

    def _get_query_embedding(self, query: str) -> list[float]:
        return embed_texts_local_sync([query])[0]

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return (await asyncio.to_thread(embed_texts_local_sync, [query]))[0]

    def _get_text_embedding(self, text: str) -> list[float]:
        return embed_texts_local_sync([text])[0]

    async def _aget_text_embedding(self, text: str) -> list[float]:
        return (await asyncio.to_thread(embed_texts_local_sync, [text]))[0]


def build_embedding_model(
    settings: Settings,
    emb_cfg: ResolvedOpenAICompat | None,
) -> BaseEmbedding:
    """与 `use_local_embedding` / 默认 embedding 模型对齐。"""
    if settings.use_local_embedding:
        return LocalFastembedEmbedding()
    if not emb_cfg:
        raise ValueError("未配置远程 embedding：请开启本地向量或配置默认 embedding 模型")
    return _openai_embed_model(emb_cfg)


def build_embedding_model_from_settings(settings: Settings) -> BaseEmbedding:
    """供离线同步脚本使用：不依赖数据库中的提供商记录。"""
    if settings.use_local_embedding:
        return LocalFastembedEmbedding()
    if not (settings.embedding_api_key or "").strip():
        raise ValueError(
            "未配置 EMBEDDING_API_KEY：同步向量索引需远程 embedding 或 USE_LOCAL_EMBEDDING=true"
        )
    return OpenAIEmbedding(
        model=settings.embedding_model,
        api_key=settings.embedding_api_key.strip(),
        api_base=_openai_v1_base(settings.embedding_api_base),
    )
