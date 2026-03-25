"""
Alembic 迁移运行时配置（执行 `alembic upgrade head` 时会跑本文件）。

和 `app/db/session.py` 的区别：
- 应用运行时用 **异步** `create_async_engine` + aiomysql（适合 FastAPI 路由）。
- Alembic CLI 是 **同步** 脚本，必须用 `create_engine` + pymysql（见 `Settings.sync_database_url()`）。

`target_metadata`：
- Autogenerate（`alembic revision --autogenerate`）需要拿到所有 ORM 模型的表结构。
- 因此除了 `Base` 外要 **import** `app.models.entities`，让各 `class X(Base)` 在 import 时注册到 `Base.metadata`（ noqa 避免「未使用 import」告警）。

offline / online：
- **offline**：不连库，只根据 metadata 生成 SQL 字符串（如输出到文件）；`literal_binds=True` 让参数直接写进 SQL 便于阅读。
- **online**（默认）：真实连接数据库执行迁移；`NullPool` 表示每次迁移用完即关连接，避免迁移进程里长驻连接池。
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import get_settings
from app.db.base import Base
import app.models.entities  # noqa: F401 — 注册 ORM 表到 Base.metadata

# alembic.ini 里的 [loggers] 等配置
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql` 等场景会走这里。"""
    url = get_settings().sync_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"mysql_charset": "utf8mb4"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """默认：`alembic upgrade head` 连库执行 revision 脚本。"""
    connectable = create_engine(
        get_settings().sync_database_url(),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
