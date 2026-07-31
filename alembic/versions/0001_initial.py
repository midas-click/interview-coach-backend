"""initial schema

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("interview_id", sa.String(), nullable=False),
        sa.Column("company_name", sa.String(), nullable=True),
        sa.Column("interview_stage", sa.String(), nullable=True),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("interview_id"),
    )
    op.create_index("ix_interviews_interview_id", "interviews", ["interview_id"])

    op.create_table(
        "transcripts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("interview_id", sa.String(), nullable=False),
        sa.Column("s3_bucket", sa.String(), nullable=False),
        sa.Column("s3_object_key", sa.String(), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("parsed_timeline", sa.JSON(), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.interview_id"]),
    )
    op.create_index("ix_transcripts_interview_id", "transcripts", ["interview_id"])

    op.create_table(
        "questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("interview_id", sa.String(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("speaker", sa.String(), nullable=True),
        sa.Column("start_time", sa.Float(), nullable=True),
        sa.Column("end_time", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.interview_id"]),
    )
    op.create_index("ix_questions_interview_id", "questions", ["interview_id"])

    op.create_table(
        "answers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("interview_id", sa.String(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("speaker", sa.String(), nullable=True),
        sa.Column("start_time", sa.Float(), nullable=True),
        sa.Column("end_time", sa.Float(), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.interview_id"]),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
    )
    op.create_index("ix_answers_interview_id", "answers", ["interview_id"])

    op.create_table(
        "interview_analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("interview_id", sa.String(), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("dimensions", sa.JSON(), nullable=False),
        sa.Column("summary", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("prompt_version", sa.String(), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.interview_id"]),
    )
    op.create_index(
        "ix_interview_analyses_interview_id", "interview_analyses", ["interview_id"]
    )

    op.create_table(
        "english_analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("interview_id", sa.String(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("mistakes", sa.JSON(), nullable=False),
        sa.Column("summary", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("prompt_version", sa.String(), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.interview_id"]),
    )
    op.create_index("ix_english_analyses_interview_id", "english_analyses", ["interview_id"])

    op.create_table(
        "vocabulary_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("interview_id", sa.String(), nullable=False),
        sa.Column("phrase", sa.String(), nullable=False),
        sa.Column("meaning", sa.String(), nullable=False),
        sa.Column("example", sa.String(), nullable=True),
        sa.Column("difficulty", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("frequency", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.interview_id"]),
    )
    op.create_index("ix_vocabulary_items_interview_id", "vocabulary_items", ["interview_id"])

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("interview_id", sa.String(), nullable=False),
        sa.Column("strengths", sa.JSON(), nullable=False),
        sa.Column("weaknesses", sa.JSON(), nullable=False),
        sa.Column("learning_plan", sa.JSON(), nullable=False),
        sa.Column("english_practice", sa.JSON(), nullable=False),
        sa.Column("technical_topics", sa.JSON(), nullable=False),
        sa.Column("summary", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("prompt_version", sa.String(), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.interview_id"]),
    )
    op.create_index("ix_recommendations_interview_id", "recommendations", ["interview_id"])

    op.create_table(
        "metrics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("interview_id", sa.String(), nullable=False),
        sa.Column("avg_answer_length", sa.Float(), nullable=True),
        sa.Column("words_per_minute", sa.Float(), nullable=True),
        sa.Column("longest_answer", sa.Float(), nullable=True),
        sa.Column("shortest_answer", sa.Float(), nullable=True),
        sa.Column("speaking_ratio", sa.Float(), nullable=True),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("answer_count", sa.Integer(), nullable=False),
        sa.Column("repeated_words", sa.JSON(), nullable=False),
        sa.Column("filler_words", sa.JSON(), nullable=False),
        sa.Column("pauses", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.interview_id"]),
    )
    op.create_index("ix_metrics_interview_id", "metrics", ["interview_id"])

    op.create_table(
        "learning_topics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recommendation_id", sa.Uuid(), nullable=False),
        sa.Column("topic", sa.String(), nullable=False),
        sa.Column("priority", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["recommendation_id"], ["recommendations.id"]),
    )
    op.create_index(
        "ix_learning_topics_recommendation_id", "learning_topics", ["recommendation_id"]
    )


def downgrade() -> None:
    op.drop_table("learning_topics")
    op.drop_table("metrics")
    op.drop_table("recommendations")
    op.drop_table("vocabulary_items")
    op.drop_table("english_analyses")
    op.drop_table("interview_analyses")
    op.drop_table("answers")
    op.drop_table("questions")
    op.drop_table("transcripts")
    op.drop_table("interviews")
