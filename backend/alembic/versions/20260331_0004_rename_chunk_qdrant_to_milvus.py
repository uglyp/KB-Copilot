"""rename chunks.qdrant_point_id to milvus_point_id

Revision ID: 20260331_0004
Revises: 20260326_0003
Create Date: 2026-03-31

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260331_0004"
down_revision: Union[str, None] = "20260326_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "chunks",
        "qdrant_point_id",
        new_column_name="milvus_point_id",
        existing_type=sa.String(length=64),
        existing_nullable=False,
    )
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        op.execute(
            sa.text(
                "ALTER TABLE chunks RENAME INDEX ix_chunks_qdrant_point_id TO ix_chunks_milvus_point_id"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        op.execute(
            sa.text(
                "ALTER TABLE chunks RENAME INDEX ix_chunks_milvus_point_id TO ix_chunks_qdrant_point_id"
            )
        )
    op.alter_column(
        "chunks",
        "milvus_point_id",
        new_column_name="qdrant_point_id",
        existing_type=sa.String(length=64),
        existing_nullable=False,
    )
