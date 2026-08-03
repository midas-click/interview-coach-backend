"""Vocabulary Agent — extracts useful phrases from interviewer speech."""

from __future__ import annotations

from models.agent_outputs import VocabularyResult
from sdk.agent import AgentContext, BaseAgent


class VocabularyAgent(BaseAgent):
    """Extracts reusable English phrases from the interviewer's speech."""

    name = "vocabulary"
    prompt_name = "vocabulary"

    async def _execute(self, context: AgentContext) -> dict:
        prompt = self._prompts.render(
            self.prompt_name,
            interview_id=context.interview_id,
            transcript=self._transcript_json(context.transcript),
        )
        response = await self._llm.complete_json(
            system=prompt,
            user="Extract useful phrases from the interviewer's speech.",
        )
        return VocabularyResult.model_validate(response.parsed).model_dump()
