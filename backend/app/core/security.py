"""
认证相关：密码哈希与 JWT。

- 密码：bcrypt 单向哈希，数据库存 `hashed_password`，**绝不**存明文。
- JWT：无状态令牌，`sub` 一般放用户 id；前端放在 `Authorization: Bearer <token>`。
- `python-jose` 的 `JWTError`：签名错误、过期、格式不对时 decode 失败，返回 None 由上层返回 401。
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings


def hash_password(password: str) -> str:
    """生成随机盐并哈希；同一密码两次调用结果不同是正常的（盐不同）。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """常量时间比较，降低时序攻击风险（bcrypt 内部已处理）。"""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(subject: str | int, extra: dict[str, Any] | None = None) -> str:
    """签发访问令牌；`exp` 使用 UTC 时间戳，与 `jwt.decode` 校验一致。"""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    to_encode: dict[str, Any] = {"sub": str(subject), "exp": expire}
    if extra:
        to_encode.update(extra)
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any] | None:
    """解析成功返回 payload；失败返回 None（不要向客户端泄露具体原因）。"""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
