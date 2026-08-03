"""add question_reviews table

Revision ID: 0002
Revises: 0001
Create Date: 2025-07-31 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "question_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("interview_id", sa.String(), nullable=False),
        sa.Column("reviews", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.interview_id"]),
    )
    op.create_index(
        "ix_question_reviews_interview_id", "question_reviews", ["interview_id"]
    )


def downgrade() -> None:
    op.drop_table("question_reviews")
