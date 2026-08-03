"""Agent output persistence: analyses, vocabulary, metrics, recommendations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from database.models import (
    EnglishAnalysis,
    InterviewAnalysis,
    LearningTopic,
    Metrics,
    QuestionReview,
    Recommendation,
    TranscriptCorrection,
    VocabularyItem,
)

SessionFactory = Callable[[], Session]


class AnalysisRepository:
    """Owns all agent-produced analytics rows (idempotent upserts / replace-all)."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    # ── interview analysis ──────────────────────────────────────────────

    def upsert_interview_analysis(
        self,
        interview_id: str,
        *,
        overall_score: float | None,
        dimensions: dict[str, Any],
        summary: str | None,
        model: str | None,
        prompt_version: str | None,
        raw: dict[str, Any],
    ) -> InterviewAnalysis:
        return self._upsert(
            InterviewAnalysis,
            interview_id,
            overall_score=overall_score,
            dimensions=dimensions,
            summary=summary,
            model=model,
            prompt_version=prompt_version,
            raw=raw,
        )

    def get_interview_analysis(self, interview_id: str) -> InterviewAnalysis | None:
        with self._session_factory() as session:
            return session.execute(
                select(InterviewAnalysis).where(
                    InterviewAnalysis.interview_id == interview_id
                )
            ).scalar_one_or_none()

    # ── english analysis ────────────────────────────────────────────────

    def upsert_english_analysis(
        self,
        interview_id: str,
        *,
        metrics: dict[str, Any],
        mistakes: list[dict[str, Any]],
        summary: str | None,
        model: str | None,
        prompt_version: str | None,
        raw: dict[str, Any],
    ) -> EnglishAnalysis:
        return self._upsert(
            EnglishAnalysis,
            interview_id,
            metrics=metrics,
            mistakes=mistakes,
            summary=summary,
            model=model,
            prompt_version=prompt_version,
            raw=raw,
        )

    def get_english_analysis(self, interview_id: str) -> EnglishAnalysis | None:
        with self._session_factory() as session:
            return session.execute(
                select(EnglishAnalysis).where(EnglishAnalysis.interview_id == interview_id)
            ).scalar_one_or_none()

    # ── vocabulary ──────────────────────────────────────────────────────

    def replace_vocabulary(self, interview_id: str, items: list[dict[str, Any]]) -> None:
        with self._session_factory() as session:
            session.execute(
                delete(VocabularyItem).where(VocabularyItem.interview_id == interview_id)
            )
            session.add_all(
                [
                    VocabularyItem(
                        interview_id=interview_id,
                        phrase=item["phrase"],
                        meaning=item["meaning"],
                        example=item.get("example"),
                        difficulty=item.get("difficulty"),
                        category=item.get("category"),
                        frequency=item.get("frequency"),
                    )
                    for item in items
                ]
            )
            session.commit()

    def get_vocabulary(self, interview_id: str) -> list[VocabularyItem]:
        with self._session_factory() as session:
            return list(
                session.execute(
                    select(VocabularyItem).where(
                        VocabularyItem.interview_id == interview_id
                    )
                ).scalars()
            )

    # ── metrics ─────────────────────────────────────────────────────────

    def upsert_metrics(self, interview_id: str, **values: Any) -> Metrics:
        row = self._upsert(Metrics, interview_id, **values)
        return row  # type: ignore[return-value]

    def get_metrics(self, interview_id: str) -> Metrics | None:
        with self._session_factory() as session:
            return session.execute(
                select(Metrics).where(Metrics.interview_id == interview_id)
            ).scalar_one_or_none()

    # ── question reviews ───────────────────────────────────────────

    def upsert_question_reviews(self, interview_id: str, reviews: list[dict[str, Any]]) -> QuestionReview:
        return self._upsert(QuestionReview, interview_id, reviews=reviews)

    def get_question_reviews(self, interview_id: str) -> QuestionReview | None:
        with self._session_factory() as session:
            return session.execute(
                select(QuestionReview).where(QuestionReview.interview_id == interview_id)
            ).scalar_one_or_none()

    # ── transcript corrections ────────────────────────────────────

    def upsert_transcript_corrections(
        self, interview_id: str, corrections: list[dict], corrected_transcript: list[dict]
    ) -> TranscriptCorrection:
        return self._upsert(
            TranscriptCorrection, interview_id,
            corrections=corrections, corrected_transcript=corrected_transcript,
        )

    def get_transcript_corrections(self, interview_id: str) -> TranscriptCorrection | None:
        with self._session_factory() as session:
            return session.execute(
                select(TranscriptCorrection).where(
                    TranscriptCorrection.interview_id == interview_id
                )
            ).scalar_one_or_none()

    # ── recommendation ──────────────────────────────────────────────────

    def upsert_recommendation(
        self,
        interview_id: str,
        *,
        strengths: list[dict[str, Any]],
        weaknesses: list[dict[str, Any]],
        learning_plan: list[dict[str, Any]],
        english_practice: list[dict[str, Any]],
        technical_topics: list[dict[str, Any]],
        summary: str | None,
        model: str | None,
        prompt_version: str | None,
        raw: dict[str, Any],
    ) -> Recommendation:
        return self._upsert(
            Recommendation,
            interview_id,
            strengths=strengths,
            weaknesses=weaknesses,
            learning_plan=learning_plan,
            english_practice=english_practice,
            technical_topics=technical_topics,
            summary=summary,
            model=model,
            prompt_version=prompt_version,
            raw=raw,
        )

    def replace_learning_topics(
        self, recommendation_id: Any, topics: list[dict[str, Any]]
    ) -> None:
        with self._session_factory() as session:
            session.execute(
                delete(LearningTopic).where(
                    LearningTopic.recommendation_id == recommendation_id
                )
            )
            session.add_all(
                [
                    LearningTopic(
                        recommendation_id=recommendation_id,
                        topic=item["topic"],
                        priority=item.get("priority"),
                    )
                    for item in topics
                ]
            )
            session.commit()

    def get_recommendation(self, interview_id: str) -> Recommendation | None:
        with self._session_factory() as session:
            return session.execute(
                select(Recommendation).where(
                    Recommendation.interview_id == interview_id
                )
            ).scalar_one_or_none()

    # ── helpers ─────────────────────────────────────────────────────────

    def _upsert(self, model_cls: type, interview_id: str, **values: Any) -> Any:
        with self._session_factory() as session:
            existing = session.execute(
                select(model_cls).where(model_cls.interview_id == interview_id)
            ).scalar_one_or_none()
            if existing is not None:
                for key, val in values.items():
                    setattr(existing, key, val)
            else:
                existing = model_cls(interview_id=interview_id, **values)
                session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing
