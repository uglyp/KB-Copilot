"""将消息/知识库增量写入 analytics_search_docs 并更新本地 LlamaIndex 向量索引。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import Settings, get_settings, mysql_url_and_connect_args
from app.services.llama_analytics.embed_factory import build_embedding_model_from_settings

logger = logging.getLogger(__name__)


def create_writer_engine(settings: Settings | None = None) -> Engine:
    """写入 analytics_* 须使用应用库同步 URL（非只读 LlamaIndex 账号）。"""
    s = settings or get_settings()
    url = s.sync_database_url()
    if url.startswith("mysql+"):
        clean, ca = mysql_url_and_connect_args(url)
        return create_engine(clean, connect_args=ca, pool_pre_ping=True)
    return create_engine(url, pool_pre_ping=True)


def _cursor_get(conn: Any, key: str) -> int | None:
    r = conn.execute(
        text("SELECT last_id FROM analytics_sync_cursor WHERE source_key = :k"),
        {"k": key},
    ).scalar()
    return int(r) if r is not None else None


def _cursor_set(conn: Any, key: str, last_id: int) -> None:
    dialect = conn.engine.dialect.name
    if dialect == "postgresql":
        conn.execute(
            text(
                """
                INSERT INTO analytics_sync_cursor (source_key, last_id, updated_at)
                VALUES (:k, :lid, CURRENT_TIMESTAMP)
                ON CONFLICT (source_key) DO UPDATE SET
                  last_id = EXCLUDED.last_id,
                  updated_at = CURRENT_TIMESTAMP
                """
            ),
            {"k": key, "lid": last_id},
        )
    else:
        conn.execute(
            text(
                """
                INSERT INTO analytics_sync_cursor (source_key, last_id, updated_at)
                VALUES (:k, :lid, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE last_id = VALUES(last_id), updated_at = CURRENT_TIMESTAMP
                """
            ),
            {"k": key, "lid": last_id},
        )


def _upsert_doc(
    conn: Any,
    *,
    source: str,
    ref_id: str,
    user_id: int,
    doc_text: str,
) -> None:
    dialect = conn.engine.dialect.name
    if dialect == "postgresql":
        conn.execute(
            text(
                """
                INSERT INTO analytics_search_docs (source, ref_id, user_id, text, updated_at)
                VALUES (:source, :ref_id, :uid, :txt, CURRENT_TIMESTAMP)
                ON CONFLICT (source, ref_id) DO UPDATE SET
                  user_id = EXCLUDED.user_id,
                  text = EXCLUDED.text,
                  updated_at = CURRENT_TIMESTAMP
                """
            ),
            {"source": source, "ref_id": ref_id, "uid": user_id, "txt": doc_text},
        )
    else:
        conn.execute(
            text(
                """
                INSERT INTO analytics_search_docs (source, ref_id, user_id, text, updated_at)
                VALUES (:source, :ref_id, :uid, :txt, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE user_id = VALUES(user_id), text = VALUES(text),
                  updated_at = CURRENT_TIMESTAMP
                """
            ),
            {"source": source, "ref_id": ref_id, "uid": user_id, "txt": doc_text},
        )


def sync_tables_incremental(settings: Settings | None = None) -> dict[str, int]:
    """拉取增量行写入 analytics_search_docs；返回各来源写入条数估计。"""
    s = settings or get_settings()
    eng = create_writer_engine(s)
    counts = {"messages": 0, "knowledge_bases": 0}
    batch = max(1, s.llamaindex_sync_batch_size)
    max_len = max(200, s.llamaindex_message_text_max_len)

    with eng.connect() as conn:
        with conn.begin():
            last_m = _cursor_get(conn, "messages") or 0
            rows = conn.execute(
                text(
                    """
                    SELECT m.id, m.role, m.content, c.user_id
                    FROM messages m
                    JOIN conversations c ON c.id = m.conversation_id
                    WHERE m.id > :last_id
                    ORDER BY m.id ASC
                    LIMIT :lim
                    """
                ),
                {"last_id": last_m, "lim": batch},
            ).mappings().all()
            max_mid = last_m
            for r in rows:
                content = (r["content"] or "")[:max_len]
                doc_text = f"[{r['role']}] {content}"
                _upsert_doc(
                    conn,
                    source="message",
                    ref_id=f"msg:{r['id']}",
                    user_id=int(r["user_id"]),
                    doc_text=doc_text,
                )
                counts["messages"] += 1
                max_mid = max(max_mid, int(r["id"]))
            if rows:
                _cursor_set(conn, "messages", max_mid)

            last_kb = _cursor_get(conn, "knowledge_bases") or 0
            kb_rows = conn.execute(
                text(
                    """
                    SELECT id, user_id, name, description, org_id, is_org_shared, created_at
                    FROM knowledge_bases
                    WHERE id > :last_id
                    ORDER BY id ASC
                    LIMIT :lim
                    """
                ),
                {"last_id": last_kb, "lim": batch},
            ).mappings().all()
            max_kid = last_kb
            for r in kb_rows:
                desc = (r["description"] or "")[:max_len]
                doc_text = (
                    f"知识库: {r['name']}\n"
                    f"描述: {desc}\n"
                    f"组织: {r['org_id'] or ''} 共享: {r['is_org_shared']}"
                )
                _upsert_doc(
                    conn,
                    source="knowledge_base",
                    ref_id=f"kb:{r['id']}",
                    user_id=int(r["user_id"]),
                    doc_text=doc_text,
                )
                counts["knowledge_bases"] += 1
                max_kid = max(max_kid, int(r["id"]))
            if kb_rows:
                _cursor_set(conn, "knowledge_bases", max_kid)

    eng.dispose()
    return counts


def rebuild_vector_index_from_db(settings: Settings | None = None) -> int:
    """读取 analytics_search_docs 全量重建向量索引并持久化（适合首次同步或重建）。"""
    from llama_index.core import Document, StorageContext, VectorStoreIndex

    s = settings or get_settings()
    eng = create_writer_engine(s)
    emb = build_embedding_model_from_settings(s)

    persist_dir = Path(s.llamaindex_vector_persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)

    docs: list[Document] = []
    with eng.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, source, ref_id, user_id, text FROM analytics_search_docs ORDER BY id ASC"
            )
        ).mappings().all()
    for r in rows:
        docs.append(
            Document(
                text=r["text"],
                metadata={
                    "user_id": str(int(r["user_id"])),
                    "source": str(r["source"]),
                    "ref_id": str(r["ref_id"]),
                },
                id_=f"{r['source']}:{r['ref_id']}",
            )
        )
    eng.dispose()

    storage_context = StorageContext.from_defaults(persist_dir=str(persist_dir))
    index = VectorStoreIndex.from_documents(
        docs,
        embed_model=emb,
        storage_context=storage_context,
        show_progress=False,
    )
    index.storage_context.persist(persist_dir=str(persist_dir))
    return len(docs)


def run_sync_once(settings: Settings | None = None) -> dict[str, Any]:
    """增量写表后重建向量索引（简单可靠；数据量大时可改为 insert 增量）。"""
    s = settings or get_settings()
    counts = sync_tables_incremental(s)
    n = 0
    if counts["messages"] or counts["knowledge_bases"]:
        n = rebuild_vector_index_from_db(s)
    elif not Path(s.llamaindex_vector_persist_dir).exists() or not any(
        Path(s.llamaindex_vector_persist_dir).glob("*.json")
    ):
        n = rebuild_vector_index_from_db(s)
    return {"table_counts": counts, "vector_docs": n}
