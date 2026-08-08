"""English Coach — analyzes spoken English. Uses candidate speech only.

Long transcripts are processed in batches so a single model response never
hits the output token limit (which previously truncated the JSON mid-list).
Batch results are merged: mistakes are concatenated, metrics are weighted
by batch size, and one final summary is synthesized in a small LLM call.
"""

from __future__ import annotations

import json
from typing import Any

from models.agent_outputs import EnglishCoachResult
from sdk.agent import AgentContext, BaseAgent

BATCH_SIZE = 100


class EnglishCoach(BaseAgent):
    """Analyzes grammar, naturalness, fluency. Feeds only candidate speech to save tokens."""

    name = "english_coach"
    prompt_name = "english_coach"

    async def _execute(self, context: AgentContext) -> dict:
        candidate = self._filter_transcript(context.transcript, "candidate")
        segments = list(candidate.transcript)
        qa_pairs = context.previous_outputs.get("conversation_parser")

        if len(segments) <= BATCH_SIZE:
            return await self._analyze_batch(context, segments, qa_pairs)

        batches = self._chunk_segments(segments, BATCH_SIZE)
        results = [await self._analyze_batch(context, b, qa_pairs) for b in batches]
        return await self._merge_batches(context, results, batches)

    async def _analyze_batch(
        self, context: AgentContext, segments: list[Any], qa_pairs: Any
    ) -> dict:
        prompt = self._prompts.render(
            self.prompt_name,
            interview_id=context.interview_id,
            transcript=json.dumps([s.model_dump() for s in segments], indent=2),
            qa_pairs=json.dumps(qa_pairs, indent=2) if qa_pairs else "[]",
        )
        response = await self._llm.complete_json(
            system=prompt,
            user="Analyze the candidate's spoken English. Find every mistake and provide corrections.",
            max_tokens=16384,
        )
        return EnglishCoachResult.model_validate(response.parsed).model_dump()

    async def _merge_batches(
        self, context: AgentContext, results: list[dict], batches: list[list[Any]]
    ) -> dict:
        sizes = [len(b) for b in batches]
        total = sum(sizes) or 1
        metrics = {
            key: round(
                sum(r["metrics"][key] * size for r, size in zip(results, sizes)) / total,
                1,
            )
            for key in results[0]["metrics"]
        }
        mistakes: list[dict] = [m for r in results for m in r.get("mistakes", [])]

        prompt = self._prompts.render(
            "english_coach_merge",
            interview_id=context.interview_id,
            batch_summaries=json.dumps([r["summary"] for r in results], indent=2),
        )
        response = await self._llm.complete_json(
            system=prompt,
            user="Synthesize the final overall summary from the per-batch results.",
            max_tokens=1024,
        )
        summary = str(response.parsed.get("summary", ""))
        return {"metrics": metrics, "mistakes": mistakes, "summary": summary}
