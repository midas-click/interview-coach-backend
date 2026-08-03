"""InterviewUploaded workflow: download → parse → parallel analysis → recommend → persist."""

from __future__ import annotations

import asyncio
from typing import Any

import inngest

from agents import build_registry as _default_registry_factory
from common.logging import get_logger
from models.transcript import TranscriptData
from sdk.agent import AgentContext, AgentRegistry, AgentResult
from services.persistence import PersistenceService
from services.s3 import TranscriptSource
from services.transcript_preprocessor import preprocess

logger = get_logger("inngest.workflows.interview_uploaded")

ANALYSIS_AGENTS = ["interview_coach", "english_coach", "vocabulary", "metrics"]
PARSER_AGENT = "conversation_parser"
RECOMMENDER = "recommendation"


class InterviewUploadedWorkflow:

    def __init__(
        self,
        transcript_source: TranscriptSource,
        persistence: PersistenceService,
        agent_registry: AgentRegistry | None = None,
    ) -> None:
        self._source = transcript_source
        self._persist = persistence
        self._registry = agent_registry or _default_registry_factory(None, None)  # type: ignore[arg-type]

    async def run(self, payload: dict[str, Any], step: inngest.Step) -> None:
        interview_id: str = payload["interview_id"]
        bucket: str = payload["bucket"]
        object_key: str = payload["object_key"]

        # 1. Download transcript
        transcript = await self._step_download(step, bucket, object_key)

        # 2. Pre-process: merge STT fragments into coherent utterances
        cleaned = await step.run(
            "preprocess-transcript",
            lambda: preprocess(transcript).model_dump(mode="json", by_alias=True),
        )
        processed = TranscriptData.model_validate(cleaned)

        # 3. Save RAW transcript (never overwritten) + interview record
        await step.run(
            "ensure-interview",
            lambda: self._persist.ensure_interview(interview_id, transcript, bucket, object_key),
        )
        await step.run(
            "mark-processing",
            lambda: self._persist.mark_processing(interview_id),
        )

        # 4. Parse conversation (using cleaned transcript)
        parse_result = await self._step_parse(step, interview_id, processed)

        await step.run(
            "persist-parse",
            lambda: self._persist.persist_parser_result(interview_id, parse_result),
        )

        # 5. Run analysis agents in parallel
        ctx = AgentContext(
            interview_id=interview_id,
            transcript=processed,
            previous_outputs={"conversation_parser": parse_result.structured_output},
        )
        analysis_results = await self._step_analyse(step, ctx)

        for r in analysis_results:
            await step.run(
                f"persist-{r.agent}",
                lambda r=r: self._persist_analysis(interview_id, r),
            )

        # 5. Recommendation
        previous = {r.agent: r.structured_output for r in analysis_results if r.status == "success"}
        rec_result = await self._step_recommend(step, interview_id, processed, previous)

        await step.run(
            "persist-recommendation",
            lambda: self._persist.persist_recommendation(interview_id, rec_result)
            if rec_result.status == "success"
            else None,
        )

        # 6. Final status
        all_results = [parse_result, rec_result, *analysis_results]
        partial = any(r.status == "failed" for r in all_results)
        await step.run(
            "mark-completed",
            lambda: self._persist.mark_completed(interview_id, partial=partial),
        )

    # ── step helpers (each returns JSON-safe data via serialise/deserialise) ─

    async def _step_download(self, step: inngest.Step, bucket: str, key: str) -> TranscriptData:
        async def _fn():
            t = await self._source.download(bucket, key)
            return t.model_dump(mode="json", by_alias=True)
        raw = await step.run("download-transcript", _fn)
        return TranscriptData.model_validate(raw)

    async def _step_parse(self, step: inngest.Step, iid: str, t: TranscriptData) -> AgentResult:
        async def _fn():
            r = await self._run_agent(PARSER_AGENT, iid, t, {})
            return self._serialise(r)
        raw = await step.run("parse-conversation", _fn)
        return self._deserialise(raw)

    async def _step_analyse(self, step: inngest.Step, ctx: AgentContext) -> list[AgentResult]:
        async def _fn():
            results = await self._run_analyses(ctx)
            return [r.model_dump(mode="json") for r in results]
        raw = await step.run("run-analysis-agents", _fn)
        return [AgentResult.model_validate(d) for d in raw]

    async def _step_recommend(self, step: inngest.Step, iid: str, t: TranscriptData, prev: dict) -> AgentResult:
        async def _fn():
            r = await self._run_agent(RECOMMENDER, iid, t, prev)
            return self._serialise(r)
        raw = await step.run("generate-recommendation", _fn)
        return self._deserialise(raw)

    # ── agent execution ────────────────────────────────────────────────────

    async def _run_agent(
        self, name: str, iid: str, transcript: Any, prev: dict[str, Any]
    ) -> AgentResult:
        if not self._registry.has(name):
            return AgentResult(agent=name, status="skipped")
        agent = self._registry.create(name)
        return await agent.run(AgentContext(interview_id=iid, transcript=transcript, previous_outputs=prev))

    async def _run_analyses(self, context: AgentContext) -> list[AgentResult]:
        tasks = [
            self._registry.create(n).run(context)
            for n in ANALYSIS_AGENTS if self._registry.has(n)
        ]
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        results: list[AgentResult] = []
        for item in gathered:
            if isinstance(item, AgentResult):
                results.append(item)
            else:
                results.append(AgentResult(agent="unknown", status="failed", error=str(item)))
        return results

    # ── persistence dispatch ───────────────────────────────────────────────

    def _persist_analysis(self, interview_id: str, result: AgentResult) -> None:
        mapping = {
            "interview_coach": self._persist.persist_interview_analysis,
            "english_coach": self._persist.persist_english_analysis,
            "vocabulary": self._persist.persist_vocabulary,
            "metrics": self._persist.persist_metrics,
        }
        handler = mapping.get(result.agent)
        if handler and result.status == "success":
            handler(interview_id, result)

    # ── serialisation ──────────────────────────────────────────────────────

    @staticmethod
    def _serialise(r: AgentResult) -> dict[str, Any]:
        return r.model_dump(mode="json")

    @staticmethod
    def _deserialise(d: dict[str, Any]) -> AgentResult:
        return AgentResult.model_validate(d)
