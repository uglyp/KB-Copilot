"""组装管理员 NL2SQL、用户参数化统计与向量检索片段。"""

from __future__ import annotations

import logging

from app.core.config import Settings, get_settings
from app.services.llama_analytics.embed_factory import build_embedding_model
from app.services.llama_analytics.engine import create_llama_readonly_engine
from app.services.llama_analytics.intent import should_run_llama_analytics
from app.services.llama_analytics.llm_factory import build_llama_llm
from app.services.llama_analytics.sql_query import run_admin_nl2sql, run_user_safe_stats
from app.services.llama_analytics.vector_index import query_analytics_vector
from app.services.model_resolver import ResolvedOpenAICompat

logger = logging.getLogger(__name__)


def build_analytics_context_sync(
    *,
    user_id: int,
    is_admin: bool,
    user_text: str,
    emb_cfg: ResolvedOpenAICompat | None,
    chat_cfg: ResolvedOpenAICompat | None,
    settings: Settings | None = None,
) -> str:
    """在 asyncio.to_thread 中调用；返回附加到 system 的纯文本。"""
    cfg = settings or get_settings()
    if not cfg.llamaindex_enabled:
        return ""
    if not should_run_llama_analytics(user_text, cfg):
        return ""

    engine = create_llama_readonly_engine()
    if engine is None:
        logger.warning("LlamaIndex 已启用但无法构造只读 Engine")
        return ""

    parts: list[str] = []
    try:
        embed_model = build_embedding_model(cfg, emb_cfg)
    except Exception as e:
        logger.exception("构建 embedding 模型失败")
        return f"【系统数据】向量侧未就绪：{e!s}"

    try:
        if is_admin:
            if chat_cfg is not None:
                try:
                    llm = build_llama_llm(chat_cfg)
                    sql_answer = run_admin_nl2sql(engine, llm, user_text)
                    if sql_answer.strip():
                        parts.append("（管理员·自然语言问数）\n" + sql_answer.strip())
                except Exception as e:
                    parts.append(f"（管理员统计查询失败：{e!s}）")
            else:
                parts.append("（管理员统计需要可用对话模型配置）")
        else:
            parts.append(run_user_safe_stats(engine, user_id))
    finally:
        engine.dispose()

    try:
        vec = query_analytics_vector(
            question=user_text,
            embed_model=embed_model,
            persist_dir=cfg.llamaindex_vector_persist_dir,
            user_id=None if is_admin else user_id,
        )
        if vec.strip():
            parts.append(vec.strip())
    except Exception as e:
        parts.append(f"（检索副本语义检索失败：{e!s}）")

    return _finalize(parts, cfg)


def _finalize(parts: list[str], _cfg: Settings) -> str:
    cleaned = [p for p in parts if p and str(p).strip()]
    if not cleaned:
        return ""
    return (
        "【系统数据上下文】以下数据来自数据库只读视图或参数化统计；回答时数字以本段为准，勿编造。\n"
        "若用户问「使用明细」「按模型」「轮次」「token」，请优先引用下文明细项与分项数字，不要只说「知识库没有」或「无法提供」。\n"
        + "\n\n".join(cleaned)
    )
