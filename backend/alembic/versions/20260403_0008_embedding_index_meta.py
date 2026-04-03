"""单例表：记录当前向量索引对应的嵌入指纹与维度，便于切换模型时提示重建。

Revision ID: 20260403_0008
Revises: 20260402_0007
Create Date: 2026-04-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260403_0008"
down_revision: Union[str, None] = "20260402_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "embedding_index_meta",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(512), nullable=False),
        sa.Column("vector_dim", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("embedding_index_meta")
