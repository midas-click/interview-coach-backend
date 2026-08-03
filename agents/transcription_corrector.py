"""Transcription Corrector — fixes mis-transcribed words in batches."""

from __future__ import annotations

import json

from models.agent_outputs import TranscriptionCorrectionResult
from sdk.agent import AgentContext, BaseAgent

BATCH_SIZE = 10


class TranscriptionCorrector(BaseAgent):
    """Identifies STT errors. Processes in 10-segment batches to stay within token limits."""

    name = "transcription_corrector"
    prompt_name = "transcription_corrector"

    async def _execute(self, context: AgentContext) -> dict:
        segments = [s.model_dump() for s in context.transcript.transcript]

        if len(segments) <= BATCH_SIZE:
            return await self._correct_batch(context, segments, 0)

        all_corrections: list[dict] = []
        corrected_map: dict[int, dict] = {}  # global_idx → corrected segment

        for batch_start in range(0, len(segments), BATCH_SIZE):
            batch = segments[batch_start : batch_start + BATCH_SIZE]
            result = await self._correct_batch(context, batch, batch_start)
            all_corrections.extend(result["corrections"])
            for item in result["corrected_transcript"]:
                idx = item["_global_idx"]
                corrected_map[idx] = item

        corrected_transcript = [
            corrected_map.get(i, segments[i]) for i in range(len(segments))
        ]
        return {"corrections": all_corrections, "corrected_transcript": corrected_transcript}

    async def _correct_batch(
        self, context: AgentContext, segments: list[dict], offset: int
    ) -> dict:
        prompt = self._prompts.render(
            self.prompt_name,
            interview_id=context.interview_id,
            transcript=json.dumps(segments, indent=2),
        )
        response = await self._llm.complete_json(
            system=prompt,
            user="Identify mis-transcribed words. Only return corrections for segments with errors.",
            max_tokens=4096,
        )
        parsed = TranscriptionCorrectionResult.model_validate(response.parsed)

        correction_map = {c.segment_index: c.corrected_text for c in parsed.corrections}
        batch_corrections: list[dict] = []
        corrected: list[dict] = []

        for i, seg in enumerate(segments):
            global_i = i + offset
            if i in correction_map:
                corrected.append({**seg, "_global_idx": global_i, "text": correction_map[i]})
                for c in parsed.corrections:
                    if c.segment_index == i:
                        batch_corrections.append({
                            "segment_index": global_i,
                            "original_text": c.original_text,
                            "corrected_text": c.corrected_text,
                            "mis_transcribed": [m.model_dump() for m in c.mis_transcribed],
                        })
                        break
            else:
                corrected.append({**seg, "_global_idx": global_i})

        return {"corrections": batch_corrections, "corrected_transcript": corrected}
