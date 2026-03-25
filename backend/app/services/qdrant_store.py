"""
Qdrant 向量库封装。

- **嵌入式（默认）**：`QdrantClient(path=...)`，同一目录同一时刻只能一个进程打开。
- **服务模式**：配置 `QDRANT_URL`（如 `http://localhost:6333`）连接 Docker / 远程 Qdrant，可多进程，可用官方 Web UI。
- **集合 / 检索**：`ensure_collection`；按 `kb_id` 过滤；`query_points` 为新 API。
"""

import os
import threading
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client import models as qmodels
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from app.core.config import get_settings

_client: QdrantClient | None = None
_client_key: str | None = None
_client_lock = threading.Lock()


def get_qdrant() -> QdrantClient:
    """进程内单例。嵌入式 path 模式：勿多进程共用同一目录。HTTP 模式（QDRANT_URL）可多 worker。"""
    global _client, _client_key
    settings = get_settings()
    with _client_lock:
        url = (settings.qdrant_url or "").strip()
        if url:
            key = f"url:{url.rstrip('/')}"
            if _client is None or _client_key != key:
                _client = QdrantClient(url=url.rstrip("/"))
                _client_key = key
        else:
            path = os.path.abspath(settings.qdrant_path)
            os.makedirs(path, exist_ok=True)
            key = f"path:{path}"
            if _client is None or _client_key != key:
                _client = QdrantClient(path=path)
                _client_key = key
        return _client


def ensure_collection(dim: int) -> None:
    settings = get_settings()
    client = get_qdrant()
    cols = [c.name for c in client.get_collections().collections]
    if settings.qdrant_collection not in cols:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


def upsert_chunks(
    kb_id: int,
    doc_id: int,
    vectors: list[list[float]],
    payloads: list[dict[str, Any]],
    chunk_ids: list[int],
) -> list[str]:
    """Returns qdrant point ids (as strings)."""
    settings = get_settings()
    client = get_qdrant()
    ensure_collection(len(vectors[0]))
    point_ids: list[str] = []
    points: list[PointStruct] = []
    for vec, pl, cid in zip(vectors, payloads, chunk_ids, strict=True):
        pid = str(uuid.uuid4())
        point_ids.append(pid)
        pl2 = dict(pl)
        pl2["kb_id"] = kb_id
        pl2["doc_id"] = doc_id
        pl2["chunk_id"] = cid
        points.append(PointStruct(id=pid, vector=vec, payload=pl2))
    client.upsert(collection_name=settings.qdrant_collection, points=points)
    return point_ids


def search_kb(kb_id: int, vector: list[float], top_k: int) -> list[dict[str, Any]]:
    """向量近邻检索。qdrant-client 1.12+ 使用 query_points；更早版本为 search。

    若尚未有任何文档入库，集合可能不存在；先按当前查询向量维度 ensure_collection，避免 Collection not found。
    """
    if not vector:
        return []
    ensure_collection(len(vector))
    settings = get_settings()
    client = get_qdrant()
    flt = Filter(must=[FieldCondition(key="kb_id", match=MatchValue(value=kb_id))])
    name = settings.qdrant_collection

    if hasattr(client, "query_points"):
        res = client.query_points(
            collection_name=name,
            query=vector,
            query_filter=flt,
            limit=top_k,
        )
        hits = res.points
    else:
        res = client.search(  # type: ignore[union-attr]
            collection_name=name,
            query_vector=vector,
            query_filter=flt,
            limit=top_k,
        )
        hits = res

    out: list[dict[str, Any]] = []
    for hit in hits:
        out.append(
            {
                "score": hit.score,
                "payload": hit.payload or {},
                "id": str(hit.id),
            }
        )
    return out


def delete_by_doc_id(doc_id: int) -> None:
    settings = get_settings()
    client = get_qdrant()
    try:
        client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="doc_id",
                            match=qmodels.MatchValue(value=doc_id),
                        )
                    ]
                )
            ),
        )
    except Exception:
        pass
