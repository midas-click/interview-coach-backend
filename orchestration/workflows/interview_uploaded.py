"""InterviewUploaded workflow: download → correct → parse → analyse → recommend → review → persist."""

from __future__ import annotations

import asyncio
from typing import Any

import inngest

from agents import build_registry as _default_registry_factory
from common.logging import get_logger
from models.transcript import TranscriptData, TranscriptSegment
from sdk.agent import AgentContext, AgentRegistry, AgentResult
from services.persistence import PersistenceService
from services.s3 import TranscriptSource

logger = get_logger("inngest.workflows.interview_uploaded")

ANALYSIS_AGENTS = ["interview_coach", "english_coach", "vocabulary", "metrics"]


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
        iid: str = payload["interview_id"]
        bucket: str = payload.get("bucket", "")
        key: str = payload.get("object_key", "")

        # 1. Download & validate transcript
        transcript = await self._step_download(step, bucket, key)

        # 2. Create interview record (FK for everything else)
        await step.run(
            "ensure-interview",
            lambda: self._persist.ensure_interview(iid, transcript, bucket, key),
        )
        await step.run("mark-processing", lambda: self._persist.mark_processing(iid))

        # 3. Correct mis-transcribed words (candidate speech only)
        tc_result = await self._step_agent(
            step, "transcription_corrector", "correct-transcription", iid, transcript, {},
        )
        corrected = self._apply_corrections(transcript, tc_result)

        await step.run(
            "persist-corrections",
            lambda: self._persist.persist_transcript_corrections(iid, tc_result)
            if tc_result.status == "success" else None,
        )

        # 4. Parse conversation into Q&A pairs
        parse_result = await self._step_agent(
            step, "conversation_parser", "parse-conversation", iid, corrected, {},
        )
        await step.run(
            "persist-parse",
            lambda: self._persist.persist_parser_result(iid, parse_result),
        )

        # 5. Run analysis agents in parallel
        analysis_results = await self._step_analyse(
            step,
            AgentContext(
                interview_id=iid, transcript=corrected,
                previous_outputs={"conversation_parser": parse_result.structured_output},
            ),
        )
        for r in analysis_results:
            await step.run(f"persist-{r.agent}", lambda r=r: self._persist_analysis(iid, r))

        # 6. Recommendation
        prev = {r.agent: r.structured_output for r in analysis_results if r.status == "success"}
        rec_result = await self._step_agent(
            step, "recommendation", "generate-recommendation", iid, corrected, prev,
        )
        await step.run(
            "persist-recommendation",
            lambda: self._persist.persist_recommendation(iid, rec_result)
            if rec_result.status == "success" else None,
        )

        # 7. Question reviewer
        qr_result = await self._step_agent(
            step, "question_reviewer", "review-questions", iid, corrected,
            {**prev, "conversation_parser": parse_result.structured_output},
        )
        await step.run(
            "persist-question-reviews",
            lambda: self._persist.persist_question_reviews(iid, qr_result)
            if qr_result.status == "success" else None,
        )

        # 8. Final status
        partial = any(
            r.status == "failed"
            for r in [parse_result, rec_result, *analysis_results]
        )
        await step.run(
            "mark-completed",
            lambda: self._persist.mark_completed(iid, partial=partial),
        )

    # ── step helpers ───────────────────────────────────────────────────────

    async def _step_download(self, step: inngest.Step, bucket: str, key: str) -> TranscriptData:
        async def _fn():
            t = await self._source.download(bucket, key)
            return t.model_dump(mode="json", by_alias=True)
        return TranscriptData.model_validate(await step.run("download-transcript", _fn))

    async def _step_agent(
        self, step: inngest.Step, name: str, step_id: str,
        iid: str, t: TranscriptData, prev: dict,
    ) -> AgentResult:
        async def _fn():
            r = await self._run_agent(name, iid, t, prev)
            return r.model_dump(mode="json")
        return AgentResult.model_validate(await step.run(step_id, _fn))

    async def _step_analyse(self, step: inngest.Step, ctx: AgentContext) -> list[AgentResult]:
        async def _fn():
            results = await self._run_analyses(ctx)
            return [r.model_dump(mode="json") for r in results]
        return [AgentResult.model_validate(d) for d in await step.run("run-analysis-agents", _fn)]

    # ── agent execution ────────────────────────────────────────────────────

    async def _run_agent(
        self, name: str, iid: str, transcript: Any, prev: dict[str, Any],
    ) -> AgentResult:
        if not self._registry.has(name):
            return AgentResult(agent=name, status="skipped")
        return await self._registry.create(name).run(
            AgentContext(interview_id=iid, transcript=transcript, previous_outputs=prev),
        )

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

    # ── helpers ────────────────────────────────────────────────────────────

    def _persist_analysis(self, iid: str, result: AgentResult) -> None:
        mapping = {
            "interview_coach": self._persist.persist_interview_analysis,
            "english_coach": self._persist.persist_english_analysis,
            "vocabulary": self._persist.persist_vocabulary,
            "metrics": self._persist.persist_metrics,
        }
        handler = mapping.get(result.agent)
        if handler and result.status == "success":
            handler(iid, result)

    @staticmethod
    def _apply_corrections(original: TranscriptData, result: AgentResult) -> TranscriptData:
        if result.status != "success" or not result.structured_output:
            return original
        segs = result.structured_output.get("corrected_transcript", [])
        if not segs:
            return original
        clean_segs = [{k: v for k, v in s.items() if k != "_global_idx"} for s in segs]
        return TranscriptData(
            interview_id=original.interview_id,
            company_name=original.company_name,
            interview_stage=original.interview_stage,
            schema_version=original.schema_version,
            transcriber=original.transcriber,
            language=original.language,
            created_at=original.created_at,
            utterances=[TranscriptSegment.model_validate(s) for s in clean_segs],
        )
