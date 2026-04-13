"""检索副本 analytics_search_docs 的向量检索（metadata 按 user_id 过滤）。"""

from __future__ import annotations

import logging
from pathlib import Path

from llama_index.core import StorageContext, load_index_from_storage
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.vector_stores.types import FilterOperator, MetadataFilter, MetadataFilters

logger = logging.getLogger(__name__)


def _persist_has_index(persist_dir: str) -> bool:
    p = Path(persist_dir)
    if not p.is_dir():
        return False
    # StorageContext.persist 会写入若干 json（版本差异：用通配）
    return any(p.glob("*.json"))


def query_analytics_vector(
    *,
    question: str,
    embed_model: BaseEmbedding,
    persist_dir: str,
    user_id: int | None,
    similarity_top_k: int = 5,
) -> str:
    """user_id 为 None 时视为管理员，不做 metadata 过滤（可见全部检索副本）。"""
    if not _persist_has_index(persist_dir):
        return ""
    try:
        storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
        index = load_index_from_storage(
            storage_context,
            embed_model=embed_model,
        )
    except Exception:
        logger.exception("加载 LlamaIndex 向量索引失败")
        return ""

    filters: MetadataFilters | None = None
    if user_id is not None:
        filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="user_id",
                    value=str(user_id),
                    operator=FilterOperator.EQ,
                )
            ]
        )
    retriever = index.as_retriever(
        similarity_top_k=similarity_top_k,
        filters=filters,
    )
    try:
        nodes = retriever.retrieve(question)
    except Exception:
        logger.exception("检索副本向量检索失败")
        return ""
    if not nodes:
        return ""
    lines: list[str] = []
    for n in nodes:
        text = n.get_content()
        meta = n.metadata or {}
        src = meta.get("source", "")
        ref = meta.get("ref_id", "")
        lines.append(f"[检索副本 {src}:{ref}] {text}")
    return "与系统检索副本相关的片段：\n" + "\n".join(lines)
