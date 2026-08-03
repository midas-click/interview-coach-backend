"""SQLAlchemy 2.0 ORM models — normalized interviews schema."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ── Status constants ────────────────────────────────────────────────────────

class InterviewStatus:
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


# ── Tables ──────────────────────────────────────────────────────────────────

class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    interview_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    company_name: Mapped[str | None] = mapped_column(String, nullable=True)
    interview_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    language: Mapped[str] = mapped_column(String, default="en")
    status: Mapped[str] = mapped_column(String, default=InterviewStatus.UPLOADED)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Transcript(Base):
    """Raw transcript — written once, never overwritten."""

    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    interview_id: Mapped[str] = mapped_column(
        String, ForeignKey("interviews.interview_id"), unique=True, index=True
    )
    s3_bucket: Mapped[str] = mapped_column(String)
    s3_object_key: Mapped[str] = mapped_column(String)
    raw_json: Mapped[dict] = mapped_column(JSON)  # type: ignore[assignment]
    parsed_timeline: Mapped[list | None] = mapped_column(JSON, nullable=True)  # type: ignore[assignment]
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    interview_id: Mapped[str] = mapped_column(
        String, ForeignKey("interviews.interview_id"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(String)
    speaker: Mapped[str | None] = mapped_column(String, nullable=True)
    start_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_time: Mapped[float | None] = mapped_column(Float, nullable=True)


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    interview_id: Mapped[str] = mapped_column(
        String, ForeignKey("interviews.interview_id"), index=True
    )
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("questions.id"), nullable=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(String)
    speaker: Mapped[str | None] = mapped_column(String, nullable=True)
    start_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


class InterviewAnalysis(Base):
    __tablename__ = "interview_analyses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    interview_id: Mapped[str] = mapped_column(
        String, ForeignKey("interviews.interview_id"), unique=True, index=True
    )
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    dimensions: Mapped[dict] = mapped_column(JSON)  # type: ignore[assignment]
    summary: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)
    raw: Mapped[dict] = mapped_column(JSON)  # type: ignore[assignment]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EnglishAnalysis(Base):
    __tablename__ = "english_analyses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    interview_id: Mapped[str] = mapped_column(
        String, ForeignKey("interviews.interview_id"), unique=True, index=True
    )
    metrics: Mapped[dict] = mapped_column(JSON)  # type: ignore[assignment]
    mistakes: Mapped[list] = mapped_column(JSON)  # type: ignore[assignment]
    summary: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)
    raw: Mapped[dict] = mapped_column(JSON)  # type: ignore[assignment]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class VocabularyItem(Base):
    __tablename__ = "vocabulary_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    interview_id: Mapped[str] = mapped_column(
        String, ForeignKey("interviews.interview_id"), index=True
    )
    phrase: Mapped[str] = mapped_column(String)
    meaning: Mapped[str] = mapped_column(String)
    example: Mapped[str | None] = mapped_column(String, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    frequency: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class QuestionReview(Base):
    __tablename__ = "question_reviews"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    interview_id: Mapped[str] = mapped_column(
        String, ForeignKey("interviews.interview_id"), unique=True, index=True
    )
    reviews: Mapped[list] = mapped_column(JSON)  # type: ignore[assignment]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class TranscriptCorrection(Base):
    __tablename__ = "transcript_corrections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    interview_id: Mapped[str] = mapped_column(
        String, ForeignKey("interviews.interview_id"), unique=True, index=True
    )
    corrections: Mapped[list] = mapped_column(JSON)  # type: ignore[assignment]
    corrected_transcript: Mapped[list] = mapped_column(JSON)  # type: ignore[assignment]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    interview_id: Mapped[str] = mapped_column(
        String, ForeignKey("interviews.interview_id"), unique=True, index=True
    )
    strengths: Mapped[list] = mapped_column(JSON)  # type: ignore[assignment]
    weaknesses: Mapped[list] = mapped_column(JSON)  # type: ignore[assignment]
    learning_plan: Mapped[list] = mapped_column(JSON)  # type: ignore[assignment]
    english_practice: Mapped[list] = mapped_column(JSON)  # type: ignore[assignment]
    technical_topics: Mapped[list] = mapped_column(JSON)  # type: ignore[assignment]
    summary: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)
    raw: Mapped[dict] = mapped_column(JSON)  # type: ignore[assignment]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Metrics(Base):
    __tablename__ = "metrics"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    interview_id: Mapped[str] = mapped_column(
        String, ForeignKey("interviews.interview_id"), unique=True, index=True
    )
    avg_answer_length: Mapped[float | None] = mapped_column(Float, nullable=True)
    words_per_minute: Mapped[float | None] = mapped_column(Float, nullable=True)
    longest_answer: Mapped[float | None] = mapped_column(Float, nullable=True)
    shortest_answer: Mapped[float | None] = mapped_column(Float, nullable=True)
    speaking_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    answer_count: Mapped[int] = mapped_column(Integer, default=0)
    repeated_words: Mapped[list] = mapped_column(JSON)  # type: ignore[assignment]
    filler_words: Mapped[list] = mapped_column(JSON)  # type: ignore[assignment]
    pauses: Mapped[list] = mapped_column(JSON)  # type: ignore[assignment]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class LearningTopic(Base):
    __tablename__ = "learning_topics"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recommendations.id"), index=True
    )
    topic: Mapped[str] = mapped_column(String)
    priority: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
