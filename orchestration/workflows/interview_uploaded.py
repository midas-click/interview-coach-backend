"""InterviewUploaded workflow: download → parse → parallel analysis → recommend → persist.

Orchestration class — separate from the Inngest function decorator so it can
be unit-tested independently.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import inngest

from agents import build_registry as _default_registry_factory
from common.logging import get_logger
from sdk.agent import AgentContext, AgentRegistry, AgentResult
from services.persistence import PersistenceService
from services.s3 import TranscriptSource

logger = get_logger("inngest.workflows.interview_uploaded")

ANALYSIS_AGENTS = ["interview_coach", "english_coach", "vocabulary", "metrics"]
PARSER_AGENT = "conversation_parser"
RECOMMENDER = "recommendation"


class InterviewUploadedWorkflow:
    """Orchestrates the full processing pipeline for an uploaded interview."""

    def __init__(
        self,
        transcript_source: TranscriptSource,
        persistence: PersistenceService,
        agent_registry: AgentRegistry | None = None,
    ) -> None:
        self._source = transcript_source
        self._persist = persistence
        self._registry = agent_registry or _default_registry_factory(None, None)  # type: ignore[arg-type]

    # ── public entrypoint ───────────────────────────────────────────────

    async def run(self, payload: dict[str, Any], step: inngest.Step) -> None:
        interview_id: str = payload["interview_id"]
        bucket: str = payload["bucket"]
        object_key: str = payload["object_key"]

        # 1. Download transcript
        transcript = await step.run(
            "download-transcript",
            self._handler(self._source.download(bucket, object_key)),
        )

        # 2. Create interview record + save raw transcript
        transcript_json = json.loads(json.dumps(transcript.model_dump(by_alias=True), default=str))
        await step.run(
            "ensure-interview",
            lambda: self._persist.ensure_interview(
                interview_id, transcript, bucket, object_key
            ),
        )
        await step.run(
            "mark-processing",
            lambda: self._persist.mark_processing(interview_id),
        )

        # 3. Parse conversation (parser agent)
        parse_result = await step.run(
            "parse-conversation",
            self._handler(self._run_agent(PARSER_AGENT, interview_id, transcript, {})),
        )
        await step.run(
            "persist-parse",
            lambda: self._persist.persist_parser_result(interview_id, parse_result),
        )

        # 4. Run analysis agents in parallel
        agent_context = AgentContext(
            interview_id=interview_id,
            transcript=transcript,
            previous_outputs={
                "conversation_parser": parse_result.structured_output,
            },
        )
        analysis_results = await step.run(
            "run-analysis-agents",
            self._handler(self._run_analyses(agent_context)),
        )

        # 5. Persist each analysis result
        for result in analysis_results:
            await step.run(
                f"persist-{result.agent}",
                lambda r=result: self._persist_analysis(interview_id, r),
            )

        # 6. Recommendation
        previous = {}
        for r in analysis_results:
            if r.status == "success":
                previous[r.agent] = r.structured_output

        rec_context = AgentContext(
            interview_id=interview_id,
            transcript=transcript,
            previous_outputs=previous,
        )
        rec_result = await step.run(
            "generate-recommendation",
            self._handler(self._run_agent(RECOMMENDER, interview_id, transcript, previous)),
        )
        await step.run(
            "persist-recommendation",
            lambda: self._persist.persist_recommendation(interview_id, rec_result)
            if rec_result.status == "success"
            else None,
        )

        # 7. Final status
        all_results = [parse_result, rec_result, *analysis_results]
        partial = any(r.status == "failed" for r in all_results)
        await step.run(
            "mark-completed",
            lambda: self._persist.mark_completed(interview_id, partial=partial),
        )

    # ── helpers ─────────────────────────────────────────────────────────

    async def _run_agent(
        self,
        name: str,
        interview_id: str,
        transcript: Any,
        previous_outputs: dict[str, Any],
    ) -> AgentResult:
        if not self._registry.has(name):
            logger.warning("agent not registered — skipping", extra={"agent": name})
            return AgentResult(agent=name, status="skipped")
        agent = self._registry.create(name)
        context = AgentContext(
            interview_id=interview_id,
            transcript=transcript,
            previous_outputs=previous_outputs,
        )
        return await agent.run(context)

    async def _run_analyses(self, context: AgentContext) -> list[AgentResult]:
        tasks = []
        for name in ANALYSIS_AGENTS:
            if not self._registry.has(name):
                continue
            agent = self._registry.create(name)
            tasks.append(agent.run(context))
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        results: list[AgentResult] = []
        for item in gathered:
            if isinstance(item, AgentResult):
                results.append(item)
            else:
                results.append(
                    AgentResult(agent="unknown", status="failed", error=str(item))
                )
        return results

    def _persist_analysis(self, interview_id: str, result: AgentResult) -> None:
        mapping: dict[str, Any] = {
            "interview_coach": self._persist.persist_interview_analysis,
            "english_coach": self._persist.persist_english_analysis,
            "vocabulary": self._persist.persist_vocabulary,
            "metrics": self._persist.persist_metrics,
        }
        handler = mapping.get(result.agent)
        if handler and result.status == "success":
            handler(interview_id, result)

    @staticmethod
    def _handler(awaitable: Any) -> Any:
        """Wrap an awaitable in an async callable for step.run."""

        async def _wrapper() -> Any:
            return await awaitable

        return _wrapper
