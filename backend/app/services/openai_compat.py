"""
通过 HTTP 调用「OpenAI 兼容」接口（`/v1/embeddings`、`/v1/chat/completions`）。

- 使用 `httpx.AsyncClient`：与 FastAPI 同为异步栈，适合高并发。
- `stream=True` 时按行解析 SSE；解析 `delta.content`，并在末包提取 `usage`（若存在）。
- 本地向量开启时走 `local_embed`，不访问远程 embedding API。
"""

import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx

from app.core.config import get_settings
from app.services.local_embed import embed_texts_local
from app.services.model_resolver import ResolvedOpenAICompat
from app.services.usage_tokens import (
    estimate_embed_usage_for_texts,
    parse_embedding_usage,
)


def _openai_v1_base(api_base: str) -> str:
    """统一为 `.../v1`，避免用户在模型设置里填 `http://host:11434/v1` 时再拼出 `/v1/v1/...` 导致 404。"""
    b = (api_base or "").strip().rstrip("/")
    if not b:
        raise ValueError("api_base 为空")
    if b.endswith("/v1"):
        return b
    return f"{b}/v1"


@dataclass
class EmbeddingUsageInfo:
    """单次 embed 调用的 token 统计（远程 API 或本地估算）。"""
    prompt_tokens: int
    total_tokens: int
    is_estimated: bool


async def embed_texts(
    cfg: ResolvedOpenAICompat | None, texts: list[str]
) -> tuple[list[list[float]], EmbeddingUsageInfo]:
    """返回向量与用量；本地 fastembed 时 `is_estimated=True`。"""
    settings = get_settings()
    if settings.use_local_embedding:
        vecs = await embed_texts_local(texts)
        p, t = estimate_embed_usage_for_texts(texts)
        return vecs, EmbeddingUsageInfo(prompt_tokens=p, total_tokens=t, is_estimated=True)
    if not cfg:
        raise ValueError("embedding 未配置：请设置 USE_LOCAL_EMBEDDING=true 或配置默认向量模型")
    url = f"{_openai_v1_base(cfg.api_base)}/embeddings"
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}
    if cfg.extra_headers:
        headers.update(cfg.extra_headers)
    payload = {"model": cfg.model_id, "input": texts}
    t = httpx.Timeout(120.0, connect=30.0)
    async with httpx.AsyncClient(timeout=t) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    vecs = [d["embedding"] for d in data["data"]]
    pt, tt = parse_embedding_usage(data.get("usage"))
    if pt is None and tt is None:
        p2, t2 = estimate_embed_usage_for_texts(texts)
        return vecs, EmbeddingUsageInfo(prompt_tokens=p2, total_tokens=t2, is_estimated=True)
    p_final = pt if pt is not None else 0
    t_final = tt if tt is not None else p_final
    return vecs, EmbeddingUsageInfo(prompt_tokens=p_final, total_tokens=t_final, is_estimated=False)


async def chat_completion_stream(
    cfg: ResolvedOpenAICompat,
    messages: list[dict[str, str]],
) -> AsyncIterator[str | dict[str, Any]]:
    """流式：多数 yield 为文本片段；流结束后若有 usage 则再 yield `{"usage": {...}}`。"""
    url = f"{_openai_v1_base(cfg.api_base)}/chat/completions"
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}
    if cfg.extra_headers:
        headers.update(cfg.extra_headers)
    payload: dict[str, Any] = {
        "model": cfg.model_id,
        "messages": messages,
        "stream": True,
    }
    last_usage: dict[str, Any] | None = None
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or line.startswith(":"):
                    continue
                if line.startswith("data: "):
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                        u = obj.get("usage")
                        if isinstance(u, dict) and u:
                            last_usage = u
                        delta = obj["choices"][0].get("delta") or {}
                        piece = delta.get("content") or ""
                        if not piece and delta.get("reasoning_content"):
                            piece = str(delta["reasoning_content"])
                        if piece:
                            yield piece
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
    if last_usage is not None:
        yield {"usage": last_usage}


async def probe_chat(cfg: ResolvedOpenAICompat) -> None:
    """模型设置页「探测」：发极小请求验证 base_url 与 key 是否可用。"""
    url = f"{_openai_v1_base(cfg.api_base)}/chat/completions"
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}
    if cfg.extra_headers:
        headers.update(cfg.extra_headers)
    payload: dict[str, Any] = {
        "model": cfg.model_id,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 8,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()


async def probe_embedding(cfg: ResolvedOpenAICompat) -> None:
    """同上，针对 embedding 端点。"""
    url = f"{_openai_v1_base(cfg.api_base)}/embeddings"
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}
    if cfg.extra_headers:
        headers.update(cfg.extra_headers)
    payload = {"model": cfg.model_id, "input": "ping"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
