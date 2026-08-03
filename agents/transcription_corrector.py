"""Transcription Corrector — fixes mis-transcribed words from STT errors.

Only outputs corrections — the full corrected transcript is built in Python
to avoid hitting LLM token limits.
"""

from __future__ import annotations

import json

from models.agent_outputs import TranscriptionCorrectionResult
from sdk.agent import AgentContext, BaseAgent


class TranscriptionCorrector(BaseAgent):
    """Identifies STT errors. Outputs only the corrections; the workflow
    builds the corrected transcript in Python."""

    name = "transcription_corrector"
    prompt_name = "transcription_corrector"

    async def _execute(self, context: AgentContext) -> dict:
        prompt = self._prompts.render(
            self.prompt_name,
            interview_id=context.interview_id,
            transcript=json.dumps(
                [s.model_dump() for s in context.transcript.transcript], indent=2
            ),
        )
        response = await self._llm.complete_json(
            system=prompt,
            user="Identify mis-transcribed words. Only return corrections for segments with errors.",
            max_tokens=8192,
        )
        parsed = TranscriptionCorrectionResult.model_validate(response.parsed)

        # Build the corrected transcript in Python.
        segments = [s.model_dump() for s in context.transcript.transcript]
        correction_map: dict[int, str] = {}
        for c in parsed.corrections:
            correction_map[c.segment_index] = c.corrected_text

        corrected_transcript: list[dict] = []
        all_corrections: list[dict] = []
        for i, seg in enumerate(segments):
            if i in correction_map:
                corrected_transcript.append({**seg, "text": correction_map[i]})
                # Find the matching correction for the flat list.
                for c in parsed.corrections:
                    if c.segment_index == i:
                        all_corrections.append({
                            "segment_index": i,
                            "original_text": c.original_text,
                            "corrected_text": c.corrected_text,
                            "mis_transcribed": [m.model_dump() for m in c.mis_transcribed],
                        })
                        break
            else:
                corrected_transcript.append(seg)

        return {
            "corrections": all_corrections,
            "corrected_transcript": corrected_transcript,
        }
