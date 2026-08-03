"""add transcript_corrections table

Revision ID: 0003
Revises: 0002
Create Date: 2025-07-31 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "transcript_corrections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("interview_id", sa.String(), nullable=False),
        sa.Column("corrections", sa.JSON(), nullable=False),
        sa.Column("corrected_transcript", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.interview_id"]),
    )
    op.create_index(
        "ix_transcript_corrections_interview_id",
        "transcript_corrections",
        ["interview_id"],
    )


def downgrade() -> None:
    op.drop_table("transcript_corrections")
