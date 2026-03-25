"""
本地向量嵌入（fastembed），不依赖 OpenAI/DeepSeek 的 embedding API。

模型首次加载会下载权重（可能很久），故用线程锁 + 双重检查，且 **慢加载放在锁外**，
避免阻塞其它并发请求。实际推理通过 `asyncio.to_thread` 放到线程池，不阻塞事件循环。
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.core.hf_env import configure_hf_hub_env

if TYPE_CHECKING:
    pass

# 确保在首次 import fastembed 前已设置 HF_ENDPOINT / 超时等
configure_hf_hub_env()

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_model = None


def _get_model():
    """首次加载 fastembed 会下载/解压模型，可能数分钟；不得在持锁期间执行，否则阻塞其它线程。"""
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:
            return _model
    try:
        from fastembed import TextEmbedding
    except ImportError as e:
        raise RuntimeError(
            "请安装 fastembed：pip install fastembed"
        ) from e
    settings = get_settings()
    # 慢操作在锁外执行，避免长时间占锁导致其它请求饿死
    new_model = TextEmbedding(model_name=settings.local_embedding_model)
    with _lock:
        if _model is None:
            _model = new_model
        return _model


def _embed_sync(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    return [[float(x) for x in emb] for emb in model.embed(texts)]


async def embed_texts_local(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    last_err: BaseException | None = None
    for attempt in range(3):
        try:
            return await asyncio.to_thread(_embed_sync, texts)
        except Exception as e:
            last_err = e
            if attempt >= 2:
                break
            wait = 2**attempt
            logger.warning(
                "本地向量失败（第 %s 次，含网络/下载超时），%s 秒后重试: %s",
                attempt + 1,
                wait,
                e,
            )
            await asyncio.sleep(wait)
    if last_err is not None:
        raise last_err
    raise RuntimeError("embed_texts_local: unreachable")
