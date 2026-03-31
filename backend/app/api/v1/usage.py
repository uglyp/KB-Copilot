"""当前登录用户的 LLM token 用量汇总与明细。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.entities import Conversation, LlmUsageRecord, LLMModel, User

router = APIRouter(prefix="/usage", tags=["usage"])


class EndpointBucket(BaseModel):
    turns: int = 0
    embed_prompt_tokens: int = 0
    embed_total_tokens: int = 0
    chat_prompt_tokens: int = 0
    chat_completion_tokens: int = 0
    chat_total_tokens: int = 0


class ModelBucket(BaseModel):
    chat_model_id: int | None
    display_name: str | None
    turns: int = 0
    chat_prompt_tokens: int = 0
    chat_completion_tokens: int = 0
    chat_total_tokens: int = 0
    embed_prompt_tokens: int = 0
    embed_total_tokens: int = 0


class UsageSummaryOut(BaseModel):
    range_days: int
    since: datetime
    totals: EndpointBucket
    by_endpoint: dict[str, EndpointBucket]
    by_model: list[ModelBucket]


class UsageRecordOut(BaseModel):
    id: int
    created_at: datetime
    conversation_id: int
    conversation_title: str | None
    endpoint_kind: str
    chat_model_id: int | None
    model_display_name: str | None
    embed_prompt_tokens: int | None
    embed_total_tokens: int | None
    chat_prompt_tokens: int | None
    chat_completion_tokens: int | None
    chat_total_tokens: int | None
    embed_is_estimated: bool
    chat_is_estimated: bool


class UsageRecordsPage(BaseModel):
    total: int
    items: list[UsageRecordOut]


def _coalesce_int(c) -> Any:
    return func.coalesce(c, 0)


@router.get("/summary", response_model=UsageSummaryOut)
async def usage_summary(
    days: int = Query(30, ge=1, le=366),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsageSummaryOut:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # 总轮次
    r_count = await db.execute(
        select(func.count())
        .select_from(LlmUsageRecord)
        .where(LlmUsageRecord.user_id == user.id, LlmUsageRecord.created_at >= since)
    )
    total_turns = int(r_count.scalar() or 0)

    # 按 endpoint 聚合
    q_ep = (
        select(
            LlmUsageRecord.endpoint_kind,
            func.count(LlmUsageRecord.id),
            func.sum(_coalesce_int(LlmUsageRecord.embed_prompt_tokens)),
            func.sum(_coalesce_int(LlmUsageRecord.embed_total_tokens)),
            func.sum(_coalesce_int(LlmUsageRecord.chat_prompt_tokens)),
            func.sum(_coalesce_int(LlmUsageRecord.chat_completion_tokens)),
            func.sum(_coalesce_int(LlmUsageRecord.chat_total_tokens)),
        )
        .where(LlmUsageRecord.user_id == user.id, LlmUsageRecord.created_at >= since)
        .group_by(LlmUsageRecord.endpoint_kind)
    )
    r_ep = await db.execute(q_ep)
    by_ep: dict[str, EndpointBucket] = {}
    totals = EndpointBucket(turns=total_turns)
    for row in r_ep.all():
        kind, n, esum_p, esum_t, csum_p, csum_c, csum_tot = row
        b = EndpointBucket(
            turns=int(n or 0),
            embed_prompt_tokens=int(esum_p or 0),
            embed_total_tokens=int(esum_t or 0),
            chat_prompt_tokens=int(csum_p or 0),
            chat_completion_tokens=int(csum_c or 0),
            chat_total_tokens=int(csum_tot or 0),
        )
        by_ep[str(kind)] = b
        totals.embed_prompt_tokens += b.embed_prompt_tokens
        totals.embed_total_tokens += b.embed_total_tokens
        totals.chat_prompt_tokens += b.chat_prompt_tokens
        totals.chat_completion_tokens += b.chat_completion_tokens
        totals.chat_total_tokens += b.chat_total_tokens

    # 按模型聚合（仅 chat_model_id 非空）
    q_m = (
        select(
            LlmUsageRecord.chat_model_id,
            func.count(LlmUsageRecord.id),
            func.sum(_coalesce_int(LlmUsageRecord.chat_prompt_tokens)),
            func.sum(_coalesce_int(LlmUsageRecord.chat_completion_tokens)),
            func.sum(_coalesce_int(LlmUsageRecord.chat_total_tokens)),
            func.sum(_coalesce_int(LlmUsageRecord.embed_prompt_tokens)),
            func.sum(_coalesce_int(LlmUsageRecord.embed_total_tokens)),
        )
        .where(
            LlmUsageRecord.user_id == user.id,
            LlmUsageRecord.created_at >= since,
            LlmUsageRecord.chat_model_id.isnot(None),
        )
        .group_by(LlmUsageRecord.chat_model_id)
    )
    r_m = await db.execute(q_m)
    model_rows = r_m.all()
    mid_set = {int(row[0]) for row in model_rows if row[0] is not None}
    names: dict[int, str] = {}
    if mid_set:
        rm = await db.execute(select(LLMModel.id, LLMModel.display_name).where(LLMModel.id.in_(mid_set)))
        for mid, dname in rm.all():
            names[int(mid)] = str(dname)

    by_model: list[ModelBucket] = []
    for row in model_rows:
        mid, n, cp, cc, ct, ep, et = row
        mid_i = int(mid) if mid is not None else None
        by_model.append(
            ModelBucket(
                chat_model_id=mid_i,
                display_name=names.get(mid_i) if mid_i is not None else None,
                turns=int(n or 0),
                chat_prompt_tokens=int(cp or 0),
                chat_completion_tokens=int(cc or 0),
                chat_total_tokens=int(ct or 0),
                embed_prompt_tokens=int(ep or 0),
                embed_total_tokens=int(et or 0),
            )
        )
    by_model.sort(key=lambda x: x.turns, reverse=True)

    return UsageSummaryOut(
        range_days=days,
        since=since,
        totals=totals,
        by_endpoint=by_ep,
        by_model=by_model,
    )


@router.get("/records", response_model=UsageRecordsPage)
async def usage_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    conversation_id: int | None = None,
    days: int | None = Query(None, ge=1, le=366),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsageRecordsPage:
    since: datetime | None = None
    if days is not None:
        since = datetime.now(timezone.utc) - timedelta(days=days)

    filters = [LlmUsageRecord.user_id == user.id]
    if since is not None:
        filters.append(LlmUsageRecord.created_at >= since)
    if conversation_id is not None:
        filters.append(LlmUsageRecord.conversation_id == conversation_id)

    count_q = select(func.count()).select_from(LlmUsageRecord).where(*filters)
    total = int((await db.execute(count_q)).scalar() or 0)

    q = (
        select(LlmUsageRecord, Conversation.title, LLMModel.display_name)
        .join(Conversation, Conversation.id == LlmUsageRecord.conversation_id)
        .outerjoin(LLMModel, LLMModel.id == LlmUsageRecord.chat_model_id)
        .where(*filters)
        .order_by(LlmUsageRecord.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    r = await db.execute(q)
    items: list[UsageRecordOut] = []
    for rec, conv_title, model_name in r.all():
        items.append(
            UsageRecordOut(
                id=rec.id,
                created_at=rec.created_at,
                conversation_id=rec.conversation_id,
                conversation_title=conv_title,
                endpoint_kind=rec.endpoint_kind,
                chat_model_id=rec.chat_model_id,
                model_display_name=model_name,
                embed_prompt_tokens=rec.embed_prompt_tokens,
                embed_total_tokens=rec.embed_total_tokens,
                chat_prompt_tokens=rec.chat_prompt_tokens,
                chat_completion_tokens=rec.chat_completion_tokens,
                chat_total_tokens=rec.chat_total_tokens,
                embed_is_estimated=rec.embed_is_estimated,
                chat_is_estimated=rec.chat_is_estimated,
            )
        )
    return UsageRecordsPage(total=total, items=items)
