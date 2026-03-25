"""判断用户是否已配置「默认且启用」的 chat / embedding；本地向量模式下 embedding 视为就绪。"""

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import LLMModel, LLMProvider


async def _has_default(
    session: AsyncSession, user_id: int, purpose: str
) -> bool:
    q = (
        select(LLMModel.id)
        .join(LLMProvider, LLMProvider.id == LLMModel.provider_id)
        .where(
            and_(
                LLMProvider.user_id == user_id,
                LLMModel.purpose == purpose,
                LLMModel.is_default.is_(True),
                LLMModel.enabled.is_(True),
            )
        )
        .limit(1)
    )
    r = await session.execute(q)
    return r.scalar_one_or_none() is not None


async def is_chat_ready(session: AsyncSession, user_id: int) -> bool:
    return await _has_default(session, user_id, "chat")


async def is_embedding_ready(session: AsyncSession, user_id: int) -> bool:
    if get_settings().use_local_embedding:
        return True
    return await _has_default(session, user_id, "embedding")


async def is_model_ready(session: AsyncSession, user_id: int) -> tuple[bool, list[str]]:
    """对话 + 向量默认模型均就绪（知识库入库与完整 RAG 检索）。"""
    missing: list[str] = []
    if not await is_chat_ready(session, user_id):
        missing.append("chat")
    if not await is_embedding_ready(session, user_id):
        missing.append("embedding")
    return (len(missing) == 0, missing)
