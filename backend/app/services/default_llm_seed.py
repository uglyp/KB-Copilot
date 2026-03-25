"""
环境变量自动注入默认 LLM 提供商（零配置上手）。

若用户已手动创建过 `LLMProvider`，则不再自动写入，避免覆盖用户数据。
"""

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import LLMModel, LLMProvider
from app.services.crypto_keys import encrypt_secret
from app.services.model_readiness import is_embedding_ready


async def ensure_deepseek_auto_seed(db: AsyncSession, user_id: int) -> None:
    settings = get_settings()
    key = (settings.deepseek_api_key or "").strip()
    if not key:
        return

    r = await db.execute(
        select(func.count())
        .select_from(LLMProvider)
        .where(LLMProvider.user_id == user_id)
    )
    if (r.scalar_one() or 0) > 0:
        return

    base = settings.deepseek_api_base.rstrip("/")
    enc = encrypt_secret(key)
    p = LLMProvider(
        user_id=user_id,
        name="DeepSeek",
        api_base=base,
        api_key_encrypted=enc,
        provider_type="openai_compatible",
        extra_headers_json=None,
    )
    db.add(p)
    await db.flush()
    db.add(
        LLMModel(
            provider_id=p.id,
            display_name="DeepSeek Chat",
            model_id=settings.deepseek_chat_model,
            purpose="chat",
            is_default=True,
            enabled=True,
        )
    )


async def ensure_ollama_chat_seed(db: AsyncSession, user_id: int) -> None:
    """若配置了 OLLAMA_BASE + OLLAMA_CHAT_MODEL，且尚无名为 Ollama 的提供商，则自动创建（非默认 chat）。"""
    settings = get_settings()
    base = (settings.ollama_base or "").strip().rstrip("/")
    mid = (settings.ollama_chat_model or "").strip()
    if not base or not mid:
        return

    r = await db.execute(
        select(LLMProvider.id)
        .where(
            LLMProvider.user_id == user_id,
            or_(LLMProvider.name == "Ollama", LLMProvider.api_base == base),
        )
        .limit(1)
    )
    if r.scalar_one_or_none() is not None:
        return

    enc = encrypt_secret("ollama")
    p = LLMProvider(
        user_id=user_id,
        name="Ollama",
        api_base=base,
        api_key_encrypted=enc,
        provider_type="openai_compatible",
        extra_headers_json=None,
    )
    db.add(p)
    await db.flush()
    db.add(
        LLMModel(
            provider_id=p.id,
            display_name="本地 " + mid,
            model_id=mid,
            purpose="chat",
            is_default=False,
            enabled=True,
        )
    )


async def ensure_embedding_api_auto_seed(db: AsyncSession, user_id: int) -> None:
    """当未启用本地向量且配置了 EMBEDDING_API_KEY 时，自动创建 OpenAI 兼容向量提供商。"""
    settings = get_settings()
    if settings.use_local_embedding:
        return
    key = (settings.embedding_api_key or "").strip()
    if not key:
        return
    if await is_embedding_ready(db, user_id):
        return

    pid_sub = select(LLMProvider.id).where(LLMProvider.user_id == user_id)
    await db.execute(
        update(LLMModel)
        .where(LLMModel.provider_id.in_(pid_sub))
        .where(LLMModel.purpose == "embedding")
        .values(is_default=False)
    )

    base = settings.embedding_api_base.rstrip("/")
    enc = encrypt_secret(key)
    p = LLMProvider(
        user_id=user_id,
        name="Embedding（API）",
        api_base=base,
        api_key_encrypted=enc,
        provider_type="openai_compatible",
        extra_headers_json=None,
    )
    db.add(p)
    await db.flush()
    db.add(
        LLMModel(
            provider_id=p.id,
            display_name="Embedding",
            model_id=settings.embedding_model,
            purpose="embedding",
            is_default=True,
            enabled=True,
        )
    )
