"""Orchestrates persistence of all agent results into the database.

The workflow calls these methods inside Inngest steps; each method
extracts structured data from an AgentResult and delegates to the
appropriate repository.
"""

from __future__ import annotations

import json
from typing import Any

from common.logging import get_logger
from models.transcript import TranscriptData
from repositories.analyses import AnalysisRepository
from repositories.interviews import InterviewRepository
from sdk.agent import AgentResult

logger = get_logger("services.persistence")


class PersistenceService:
    """Transaction script: takes AgentResults and writes to the DB."""

    def __init__(
        self,
        interviews: InterviewRepository,
        analyses: AnalysisRepository,
    ) -> None:
        self._interviews = interviews
        self._analyses = analyses

    # ── interview setup ─────────────────────────────────────────────────

    def ensure_interview(
        self,
        interview_id: str,
        transcript: TranscriptData,
        bucket: str,
        object_key: str,
    ) -> None:
        self._interviews.create_if_missing(
            interview_id,
            company_name=transcript.company_name,
            interview_stage=transcript.interview_stage,
            language=transcript.transcriber.language,
        )
        self._interviews.save_transcript(
            interview_id,
            bucket=bucket,
            object_key=object_key,
            raw_json=transcript.model_dump(mode="json", by_alias=True),
        )

    # ── status helpers ──────────────────────────────────────────────────

    def mark_processing(self, interview_id: str) -> None:
        self._interviews.update_status(interview_id, "processing")

    def mark_completed(self, interview_id: str, *, partial: bool = False) -> None:
        self._interviews.update_status(
            interview_id, "partial" if partial else "completed"
        )

    def mark_failed(self, interview_id: str, error: str) -> None:
        self._interviews.update_status(interview_id, "failed", error_message=error)

    # ── parser ──────────────────────────────────────────────────────────

    def persist_parser_result(
        self, interview_id: str, result: AgentResult
    ) -> None:
        output: dict[str, Any] = result.structured_output or {}
        questions: list[dict[str, Any]] = output.get("questions", [])
        answers: list[dict[str, Any]] = output.get("answers", [])

        self._interviews.replace_questions(interview_id, questions)

        # Build mapping: parser question id → DB question id
        db_questions = self._interviews.get_questions(interview_id)
        q_ref_to_id: dict[str, Any] = {}
        for i, q in enumerate(questions):
            if i < len(db_questions):
                q_ref_to_id[q["id"]] = db_questions[i].id

        self._interviews.replace_answers(interview_id, answers, q_ref_to_id)

    # ── analysis agents ─────────────────────────────────────────────────

    def persist_interview_analysis(
        self, interview_id: str, result: AgentResult
    ) -> None:
        output: dict[str, Any] = result.structured_output or {}
        self._analyses.upsert_interview_analysis(
            interview_id,
            overall_score=output.get("overall_score"),
            dimensions=output.get("dimensions", {}),
            summary=output.get("summary"),
            model=result.model,
            prompt_version=result.prompt_version,
            raw=output,
        )

    def persist_english_analysis(
        self, interview_id: str, result: AgentResult
    ) -> None:
        output: dict[str, Any] = result.structured_output or {}
        self._analyses.upsert_english_analysis(
            interview_id,
            metrics=output.get("metrics", {}),
            mistakes=output.get("mistakes", []),
            summary=output.get("summary"),
            model=result.model,
            prompt_version=result.prompt_version,
            raw=output,
        )

    def persist_vocabulary(
        self, interview_id: str, result: AgentResult
    ) -> None:
        output: dict[str, Any] = result.structured_output or {}
        self._analyses.replace_vocabulary(
            interview_id, output.get("phrases", [])
        )

    def persist_metrics(
        self, interview_id: str, result: AgentResult
    ) -> None:
        output: dict[str, Any] = result.structured_output or {}
        self._analyses.upsert_metrics(interview_id, **output)

    def persist_recommendation(
        self, interview_id: str, result: AgentResult
    ) -> None:
        output: dict[str, Any] = result.structured_output or {}
        rec = self._analyses.upsert_recommendation(
            interview_id,
            strengths=output.get("strengths", []),
            weaknesses=output.get("weaknesses", []),
            learning_plan=output.get("learning_plan", []),
            english_practice=output.get("english_practice", []),
            technical_topics=output.get("technical_topics", []),
            summary=output.get("summary"),
            model=result.model,
            prompt_version=result.prompt_version,
            raw=output,
        )
        topics: list[dict[str, Any]] = [
            {"topic": t.get("topic", ""), "priority": t.get("priority")}
            for t in output.get("technical_topics", [])
        ]
        if topics:
            self._analyses.replace_learning_topics(rec.id, topics)

    def persist_question_reviews(
        self, interview_id: str, result: AgentResult
    ) -> None:
        output: dict[str, Any] = result.structured_output or {}
        self._analyses.upsert_question_reviews(
            interview_id, output.get("reviews", [])
        )

    def persist_transcript_corrections(
        self, interview_id: str, result: AgentResult
    ) -> None:
        output: dict[str, Any] = result.structured_output or {}
        self._analyses.upsert_transcript_corrections(
            interview_id,
            output.get("corrections", []),
            output.get("corrected_transcript", []),
        )
