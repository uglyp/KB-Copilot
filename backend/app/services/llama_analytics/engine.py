"""只读同步 Engine：供 LlamaIndex SQLDatabase / 向量查询使用。"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.core.config import get_settings, mysql_url_and_connect_args


def create_llama_readonly_engine() -> Engine | None:
    """使用 LLAMAINDEX_DATABASE_URL 或（启用时）应用库 sync URL。"""
    settings = get_settings()
    url = settings.llamaindex_effective_database_url()
    if not url:
        return None
    if url.startswith("mysql+"):
        clean, ca = mysql_url_and_connect_args(url)
        return create_engine(clean, connect_args=ca, pool_pre_ping=True, pool_size=2)
    return create_engine(url, pool_pre_ping=True, pool_size=2)
