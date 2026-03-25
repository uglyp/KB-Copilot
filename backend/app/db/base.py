"""
ORM 模型基类。所有 `DeclarativeBase` 子类会注册到同一 metadata，供 Alembic `autogenerate` 比对表结构。
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
