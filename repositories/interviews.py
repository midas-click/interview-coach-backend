"""Interview lifecycle + raw transcript + parsed Q/A persistence."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from database.models import (
    Answer, EnglishAnalysis, Interview, InterviewAnalysis,
    LearningTopic, Metrics, Question, QuestionReview,
    Recommendation, Transcript, TranscriptCorrection, VocabularyItem,
)

SessionFactory = Callable[[], Session]


class InterviewRepository:
    """Owns interview records, raw transcripts (never overwritten), and
    parsed question/answer rows (replace-all for idempotent re-parses)."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    # ── interviews ──────────────────────────────────────────────────────

    def get(self, interview_id: str) -> Interview | None:
        with self._session_factory() as session:
            return session.execute(
                select(Interview).where(Interview.interview_id == interview_id)
            ).scalar_one_or_none()

    def list(self, limit: int = 50, offset: int = 0) -> list[Interview]:
        with self._session_factory() as session:
            return list(
                session.execute(
                    select(Interview)
                    .order_by(Interview.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                ).scalars()
            )

    def create_if_missing(
        self,
        interview_id: str,
        *,
        company_name: str | None,
        interview_stage: str | None,
        language: str,
    ) -> Interview:
        with self._session_factory() as session:
            existing = session.execute(
                select(Interview).where(Interview.interview_id == interview_id)
            ).scalar_one_or_none()
            if existing is None:
                existing = Interview(
                    interview_id=interview_id,
                    company_name=company_name,
                    interview_stage=interview_stage,
                    language=language,
                )
                session.add(existing)
                session.commit()
                session.refresh(existing)
            return existing

    def update_status(
        self, interview_id: str, status: str, *, error_message: str | None = None
    ) -> None:
        with self._session_factory() as session:
            interview = session.execute(
                select(Interview).where(Interview.interview_id == interview_id)
            ).scalar_one_or_none()
            if interview is None:
                return
            interview.status = status
            interview.error_message = error_message
            session.commit()

    # ── raw transcript ──────────────────────────────────────────────────

    def save_transcript(
        self,
        interview_id: str,
        *,
        bucket: str,
        object_key: str,
        raw_json: dict[str, Any],
        parsed_timeline: list[dict[str, Any]] | None = None,
    ) -> None:
        with self._session_factory() as session:
            # Clear stale analysis data so a fresh run starts clean.
            self._clear_analyses(session, interview_id)

            existing = session.execute(
                select(Transcript).where(Transcript.interview_id == interview_id)
            ).scalar_one_or_none()
            if existing is not None:
                existing.s3_bucket = bucket
                existing.s3_object_key = object_key
                existing.raw_json = raw_json
                existing.parsed_timeline = parsed_timeline
            else:
                session.add(
                    Transcript(
                        interview_id=interview_id,
                        s3_bucket=bucket,
                        s3_object_key=object_key,
                        raw_json=raw_json,
                        parsed_timeline=parsed_timeline,
                    )
                )
            session.commit()

    def get_transcript(self, interview_id: str) -> Transcript | None:
        with self._session_factory() as session:
            return session.execute(
                select(Transcript).where(Transcript.interview_id == interview_id)
            ).scalar_one_or_none()

    # ── clear analyses for fresh run ────────────────────────────────────

    @staticmethod
    def _clear_analyses(session: Session, interview_id: str) -> None:
        """Delete all analysis data so a fresh workflow starts clean."""
        # Delete children before parents (FK order).
        session.execute(
            delete(LearningTopic).where(
                LearningTopic.recommendation_id.in_(
                    select(Recommendation.id).where(Recommendation.interview_id == interview_id)
                )
            )
        )
        for model in [
            InterviewAnalysis, EnglishAnalysis, VocabularyItem,
            QuestionReview, TranscriptCorrection, Recommendation,
            Metrics,
        ]:
            session.execute(delete(model).where(model.interview_id == interview_id))
        session.flush()

    # ── Q / A ───────────────────────────────────────────────────────────

    def replace_questions(self, interview_id: str, questions: list[dict[str, Any]]) -> None:
        with self._session_factory() as session:
            session.execute(delete(Answer).where(Answer.interview_id == interview_id))
            session.execute(delete(Question).where(Question.interview_id == interview_id))
            session.add_all(
                [
                    Question(
                        interview_id=interview_id,
                        sequence=item["sequence"],
                        text=item["text"],
                        speaker=item.get("speaker"),
                        start_time=item.get("start"),
                        end_time=item.get("end"),
                    )
                    for item in questions
                ]
            )
            session.commit()

    def replace_answers(
        self,
        interview_id: str,
        answers: list[dict[str, Any]],
        question_ids_by_ref: dict[str, Any],
    ) -> None:
        with self._session_factory() as session:
            session.execute(delete(Answer).where(Answer.interview_id == interview_id))
            session.add_all(
                [
                    Answer(
                        interview_id=interview_id,
                        question_id=question_ids_by_ref.get(item.get("question_id")),
                        sequence=item["sequence"],
                        text=item["text"],
                        speaker=item.get("speaker"),
                        start_time=item.get("start"),
                        end_time=item.get("end"),
                        duration=item.get("duration"),
                        word_count=item.get("word_count"),
                    )
                    for item in answers
                ]
            )
            session.commit()

    def get_questions(self, interview_id: str) -> list[Question]:
        with self._session_factory() as session:
            return list(
                session.execute(
                    select(Question)
                    .where(Question.interview_id == interview_id)
                    .order_by(Question.sequence)
                ).scalars()
            )

    def get_answers(self, interview_id: str) -> list[Answer]:
        with self._session_factory() as session:
            return list(
                session.execute(
                    select(Answer)
                    .where(Answer.interview_id == interview_id)
                    .order_by(Answer.sequence)
                ).scalars()
            )

    def delete(self, interview_id: str) -> bool:
        """Delete an interview and all related records. Returns True if deleted."""
        with self._session_factory() as session:
            interview = session.execute(
                select(Interview).where(Interview.interview_id == interview_id)
            ).scalar_one_or_none()
            if interview is None:
                return False

            # Delete in dependency order: children first, then parent
            from database.models import (
                Answer, EnglishAnalysis, InterviewAnalysis, LearningTopic,
                Metrics, Question, QuestionReview, Recommendation,
                Transcript, TranscriptCorrection, VocabularyItem,
            )

            # Learning topics reference recommendations by UUID
            rec = session.execute(
                select(Recommendation).where(Recommendation.interview_id == interview_id)
            ).scalar_one_or_none()
            if rec:
                session.execute(delete(LearningTopic).where(LearningTopic.recommendation_id == rec.id))

            # All tables with interview_id FK
            for model in [
                Answer, Question, Transcript,
                InterviewAnalysis, EnglishAnalysis, VocabularyItem,
                QuestionReview, TranscriptCorrection, Recommendation, Metrics,
            ]:
                session.execute(delete(model).where(model.interview_id == interview_id))

            session.delete(interview)
            session.commit()
            return True
