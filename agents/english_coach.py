"""English Coach — analyzes spoken English and provides corrections."""

from __future__ import annotations

import json

from models.agent_outputs import EnglishCoachResult
from sdk.agent import AgentContext, BaseAgent


class EnglishCoach(BaseAgent):
    """Analyzes grammar, naturalness, fluency, and provides corrective feedback."""

    name = "english_coach"
    prompt_name = "english_coach"

    async def _execute(self, context: AgentContext) -> dict:
        qa_pairs = context.previous_outputs.get("conversation_parser")
        prompt = self._prompts.render(
            self.prompt_name,
            interview_id=context.interview_id,
            transcript=self._transcript_json(context.transcript),
            qa_pairs=json.dumps(qa_pairs, indent=2) if qa_pairs else "[]",
        )
        response = await self._llm.complete_json(
            system=prompt,
            user="Analyze the candidate's spoken English. Return only the top 15 mistakes, not all.",
            max_tokens=8192,
        )
        return EnglishCoachResult.model_validate(response.parsed).model_dump()
