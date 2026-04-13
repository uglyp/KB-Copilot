#!/usr/bin/env python3
"""增量同步消息/知识库到 analytics_search_docs 并重建 LlamaIndex 向量索引。

使用应用库同步 URL（DATABASE_URL 对应的 mysql+pymysql / postgresql+psycopg），
需具备对 analytics_* 表的写入权限；与只读 LLAMAINDEX_DATABASE_URL 分离。

用法（在 backend 目录）::

    uv run python scripts/sync_analytics_index.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> int:
    from app.services.llama_analytics.sync import run_sync_once

    out = run_sync_once()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
