"""Vocabulary Agent — extracts phrases from interviewer speech only."""

from __future__ import annotations

from models.agent_outputs import VocabularyResult
from sdk.agent import AgentContext, BaseAgent


class VocabularyAgent(BaseAgent):
    """Extracts reusable English phrases. Feeds only interviewer speech."""

    name = "vocabulary"
    prompt_name = "vocabulary"

    async def _execute(self, context: AgentContext) -> dict:
        interviewer = self._filter_transcript(context.transcript, "interviewer")
        prompt = self._prompts.render(
            self.prompt_name,
            interview_id=context.interview_id,
            transcript=self._transcript_json(interviewer),
        )
        response = await self._llm.complete_json(
            system=prompt,
            user="Extract useful phrases from the interviewer's speech.",
            max_tokens=16384,
        )
        return VocabularyResult.model_validate(response.parsed).model_dump()
