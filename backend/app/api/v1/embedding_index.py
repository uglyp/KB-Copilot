"""向量索引与嵌入模型一致性：状态查询、管理员一键重建 Milvus 集合并全量重入库。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.entities import User
from app.services.embedding_index_state import (
    admin_rebuild_embedding_index,
    full_status,
)

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/embedding-index/status")
async def embedding_index_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """含一次嵌入探测与 Milvus 维度对比，供模型设置页展示。"""
    return await full_status(db, user.id)


class RebuildBody(BaseModel):
    confirm: bool = Field(
        default=False,
        description="必须为 true；将删除当前 Milvus 集合并对所有就绪文档重新向量化",
    )


@router.post("/embedding-index/rebuild")
async def embedding_index_rebuild(
    body: RebuildBody,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """仅管理员。删除实例级 Milvus 集合后，按文档表 status=ready 全量重跑入库。"""
    if not body.confirm:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="请在请求体中设置 confirm: true 以确认重建（将清空当前向量集合并重新入库）",
        )
    try:
        return await admin_rebuild_embedding_index(db, user.id)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
