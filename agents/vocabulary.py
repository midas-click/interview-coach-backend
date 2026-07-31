"""Vocabulary Agent — extracts useful phrases from interviewer speech."""

from __future__ import annotations

import json

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
            transcript=json.dumps([s.model_dump() for s in context.transcript.transcript], indent=2),
        )
        response = await self._llm.complete_json(
            system=prompt,
            user="Extract useful phrases from the interviewer's speech.",
        )
        parsed = VocabularyResult.model_validate(response.parsed)
        return parsed.model_dump()
