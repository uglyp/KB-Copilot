#!/usr/bin/env python3
"""
查看 Qdrant 中的集合与向量点（payload、向量维度与前几维预览）。

- 若使用 **QDRANT_URL**（Docker 服务）：可与 uvicorn 同时运行，无目录锁问题。
- 若使用 **嵌入式 QDRANT_PATH**：与 uvicorn 共用同一目录时需先停止后端，否则会报目录已被占用。

用法（在 backend 目录下）：

    export PYTHONPATH=.
    python scripts/inspect_qdrant.py
    python scripts/inspect_qdrant.py --limit 20
"""

from __future__ import annotations

import argparse
import os
import sys

# 保证能 import app.*
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.core.config import get_settings  # noqa: E402
from app.services.qdrant_store import get_qdrant  # noqa: E402


def _vector_dim_and_preview(vec: object) -> tuple[int, str]:
    if vec is None:
        return 0, "None"
    if isinstance(vec, dict):
        # named vectors
        parts = []
        for k, v in vec.items():
            if hasattr(v, "__len__"):
                parts.append(f"{k}: dim={len(v)} preview={list(v)[:3]}...")
        return sum(len(v) for v in vec.values() if hasattr(v, "__len__")), " | ".join(parts) or str(vec)
    if hasattr(vec, "__len__"):
        v = list(vec)
        return len(v), f"dim={len(v)} preview={v[:3]}..."
    return 0, str(vec)[:80]


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect local Qdrant storage")
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="scroll 返回的最大条数",
    )
    args = parser.parse_args()

    s = get_settings()
    name = s.qdrant_collection
    if (s.qdrant_url or "").strip():
        print(f"QDRANT_URL    = {s.qdrant_url}")
    else:
        print(f"QDRANT_PATH   = {os.path.abspath(s.qdrant_path)}")
    print(f"collection    = {name}")
    print()

    client = get_qdrant()
    cols = client.get_collections().collections
    names = [c.name for c in cols]
    print("collections:", names)
    if name not in names:
        print(f"\n集合「{name}」不存在（可能尚未有文档入库）。")
        return

    info = client.get_collection(collection_name=name)
    cnt = getattr(info, "points_count", None)
    print("points_count:", cnt)
    print()

    res = client.scroll(
        collection_name=name,
        limit=args.limit,
        with_payload=True,
        with_vectors=True,
    )
    points = res[0] if isinstance(res, (list, tuple)) else res.points

    for i, p in enumerate(points):
        dim, prev = _vector_dim_and_preview(getattr(p, "vector", None))
        print(f"--- #{i + 1} id={p.id} ---")
        print("payload:", p.payload)
        print("vector:", prev if dim else "(empty)")
    if not points:
        print("(无点，集合为空)")


if __name__ == "__main__":
    main()
