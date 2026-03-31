"""llm_usage_records: 问答轮次 token 用量

Revision ID: 20260331_0005
Revises: 20260331_0004
Create Date: 2026-03-31

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260331_0005"
down_revision: Union[str, None] = "20260331_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bool_false = sa.false()
    else:
        bool_false = sa.text("0")

    op.create_table(
        "llm_usage_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("user_message_id", sa.Integer(), nullable=False),
        sa.Column("assistant_message_id", sa.Integer(), nullable=False),
        sa.Column("chat_model_id", sa.Integer(), nullable=True),
        sa.Column("endpoint_kind", sa.String(16), nullable=False),
        sa.Column("embed_prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("embed_total_tokens", sa.Integer(), nullable=True),
        sa.Column("chat_prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("chat_completion_tokens", sa.Integer(), nullable=True),
        sa.Column("chat_total_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "embed_is_estimated", sa.Boolean(), nullable=False, server_default=bool_false
        ),
        sa.Column(
            "chat_is_estimated", sa.Boolean(), nullable=False, server_default=bool_false
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["assistant_message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chat_model_id"], ["llm_models.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_usage_records_user_id", "llm_usage_records", ["user_id"])
    op.create_index("ix_llm_usage_records_conversation_id", "llm_usage_records", ["conversation_id"])
    op.create_index("ix_llm_usage_records_chat_model_id", "llm_usage_records", ["chat_model_id"])
    op.create_index(
        "ix_llm_usage_user_created",
        "llm_usage_records",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_llm_usage_user_created", table_name="llm_usage_records")
    op.drop_index("ix_llm_usage_records_chat_model_id", table_name="llm_usage_records")
    op.drop_index("ix_llm_usage_records_conversation_id", table_name="llm_usage_records")
    op.drop_index("ix_llm_usage_records_user_id", table_name="llm_usage_records")
    op.drop_table("llm_usage_records")
