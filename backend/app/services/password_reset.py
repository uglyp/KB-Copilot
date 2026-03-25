"""忘记密码：生成随机 token，仅存 SHA256；校验后更新密码并清除该用户全部重置令牌。"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.entities import PasswordResetToken, User


def hash_reset_token(raw: str) -> str:
    """与入库时一致，对原始 token 做 SHA256 十六进制。"""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def create_password_reset_token(db: AsyncSession, user_id: int) -> str:
    """使该用户未使用的旧令牌失效，写入新令牌，返回明文 token（仅用于邮件或开发态响应）。"""
    settings = get_settings()
    raw = secrets.token_urlsafe(32)
    token_hash = hash_reset_token(raw)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.password_reset_token_ttl_minutes
    )
    await db.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
        )
    )
    db.add(
        PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
    )
    await db.flush()
    return raw


async def reset_password_with_token(
    db: AsyncSession, raw_token: str, new_password: str
) -> None:
    """校验 token，更新密码，并删除该用户所有 password_reset 行。"""
    th = hash_reset_token(raw_token.strip())
    r = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == th,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > datetime.now(timezone.utc),
        )
    )
    row = r.scalar_one_or_none()
    if not row:
        raise ValueError("INVALID_OR_EXPIRED_TOKEN")

    r2 = await db.execute(select(User).where(User.id == row.user_id))
    user = r2.scalar_one_or_none()
    if not user:
        raise ValueError("INVALID_OR_EXPIRED_TOKEN")

    user.hashed_password = hash_password(new_password)
    await db.execute(
        delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    )
    await db.flush()
