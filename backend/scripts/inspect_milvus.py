#!/usr/bin/env python3
"""
查看 Milvus 集合与实体（标量字段；向量维度见 schema 描述）。

- **MILVUS_URI**（独立服务）：可与 uvicorn 同时运行。
- **Milvus Lite（MILVUS_DB_PATH）**：多进程争用同一 `.db` 时可能失败，必要时先停后端。

用法（在 backend 目录下）::

    uv run python scripts/inspect_milvus.py
    uv run python scripts/inspect_milvus.py --limit 20
"""

from __future__ import annotations

import argparse
import os
import sys

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.core.config import get_settings  # noqa: E402
from app.services.milvus_store import get_milvus  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Milvus collection / entities")
    parser.add_argument("--limit", type=int, default=5, help="max entities to print")
    args = parser.parse_args()

    s = get_settings()
    name = s.milvus_collection
    uri = (s.milvus_uri or "").strip()
    if uri:
        print(f"MILVUS_URI    = {uri}")
        if (s.milvus_token or "").strip():
            print("MILVUS_TOKEN  = (已设置)")
    else:
        print(f"MILVUS_DB_PATH = {os.path.abspath(s.milvus_db_path)}")
    print(f"MILVUS_COLLECTION = {name}")

    client = get_milvus()
    if not client.has_collection(name):
        print("(集合不存在，尚无入库数据或未触发 ensure_collection)")
        return

    info = client.describe_collection(name)
    dim = 0
    for f in info.get("fields") or []:
        if f.get("name") == "vector":
            dim = int((f.get("params") or {}).get("dim", 0))
    print(f"vector dim    = {dim}")

    lim = max(1, min(args.limit, 500))
    rows = client.query(
        collection_name=name,
        filter="kb_id >= 0",
        limit=lim,
        output_fields=[
            "pk",
            "kb_id",
            "doc_id",
            "chunk_db_id",
            "text",
            "filename",
            "modality",
        ],
    )
    print(f"sample count  = {len(rows)} (limit={lim})")
    for i, row in enumerate(rows):
        print(f"--- [{i}] pk={row.get('pk')} kb_id={row.get('kb_id')} doc_id={row.get('doc_id')} chunk_db_id={row.get('chunk_db_id')}")
        print(f"    filename={row.get('filename')} modality={row.get('modality')}")
        txt = (row.get("text") or "")[:120]
        print(f"    text[:120]={txt!r}")


if __name__ == "__main__":
    main()
