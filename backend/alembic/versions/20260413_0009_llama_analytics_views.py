"""LlamaIndex：脱敏视图 + 检索副本表 + 同步水位表

Revision ID: 20260413_0009
Revises: 20260403_0008
Create Date: 2026-04-13

- v_*：供只读 NL2SQL 白名单使用（不含密码、密钥、storage_path）。
- analytics_*：由同步任务写入，供向量索引；应用主库迁移创建，同步脚本用 sync_database_url 写入。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260413_0009"
down_revision: Union[str, None] = "20260403_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.create_table(
        "analytics_sync_cursor",
        sa.Column("source_key", sa.String(64), nullable=False),
        sa.Column("last_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("source_key"),
    )

    op.create_table(
        "analytics_search_docs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("ref_id", sa.String(128), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analytics_search_docs_user_id", "analytics_search_docs", ["user_id"]
    )
    op.create_index(
        "uq_analytics_search_docs_source_ref",
        "analytics_search_docs",
        ["source", "ref_id"],
        unique=True,
    )

    # ---- 脱敏视图（方言分支）----
    if dialect == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE VIEW v_users_public AS
            SELECT id, username, branch, role, org_id, is_active, created_at
            FROM users
            """
        )
        op.execute(
            """
            CREATE OR REPLACE VIEW v_knowledge_bases_catalog AS
            SELECT id, user_id, name, description, org_id, is_org_shared, created_at
            FROM knowledge_bases
            """
        )
        op.execute(
            """
            CREATE OR REPLACE VIEW v_conversations_summary AS
            SELECT id, user_id, kb_id, title, created_at
            FROM conversations
            """
        )
        op.execute(
            """
            CREATE OR REPLACE VIEW v_documents_catalog AS
            SELECT id, kb_id, filename, modality, status, branch, security_level,
                   creator_user_id, created_at
            FROM documents
            """
        )
        op.execute(
            """
            CREATE OR REPLACE VIEW v_messages_for_analytics AS
            SELECT m.id AS message_id,
                   m.conversation_id,
                   c.user_id,
                   m.role,
                   SUBSTRING(m.content FROM 1 FOR 500) AS content_preview,
                   m.created_at
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            """
        )
        op.execute(
            """
            CREATE OR REPLACE VIEW v_llm_usage_records_public AS
            SELECT id, user_id, conversation_id, chat_model_id,
                   chat_total_tokens, embed_total_tokens, created_at
            FROM llm_usage_records
            """
        )
    else:
        # MySQL
        op.execute(
            """
            CREATE VIEW v_users_public AS
            SELECT id, username, branch, role, org_id, is_active, created_at
            FROM users
            """
        )
        op.execute(
            """
            CREATE VIEW v_knowledge_bases_catalog AS
            SELECT id, user_id, name, description, org_id, is_org_shared, created_at
            FROM knowledge_bases
            """
        )
        op.execute(
            """
            CREATE VIEW v_conversations_summary AS
            SELECT id, user_id, kb_id, title, created_at
            FROM conversations
            """
        )
        op.execute(
            """
            CREATE VIEW v_documents_catalog AS
            SELECT id, kb_id, filename, modality, status, branch, security_level,
                   creator_user_id, created_at
            FROM documents
            """
        )
        op.execute(
            """
            CREATE VIEW v_messages_for_analytics AS
            SELECT m.id AS message_id,
                   m.conversation_id,
                   c.user_id,
                   m.role,
                   SUBSTRING(m.content, 1, 500) AS content_preview,
                   m.created_at
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            """
        )
        op.execute(
            """
            CREATE VIEW v_llm_usage_records_public AS
            SELECT id, user_id, conversation_id, chat_model_id,
                   chat_total_tokens, embed_total_tokens, created_at
            FROM llm_usage_records
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    views = (
        "v_llm_usage_records_public",
        "v_messages_for_analytics",
        "v_documents_catalog",
        "v_conversations_summary",
        "v_knowledge_bases_catalog",
        "v_users_public",
    )
    for v in views:
        if dialect == "postgresql":
            op.execute(f"DROP VIEW IF EXISTS {v} CASCADE")
        else:
            op.execute(f"DROP VIEW IF EXISTS {v}")

    op.drop_index("uq_analytics_search_docs_source_ref", table_name="analytics_search_docs")
    op.drop_index("ix_analytics_search_docs_user_id", table_name="analytics_search_docs")
    op.drop_table("analytics_search_docs")
    op.drop_table("analytics_sync_cursor")
