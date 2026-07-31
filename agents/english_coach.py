"""English Coach — analyzes spoken English and provides corrections."""

from __future__ import annotations

import json

from models.agent_outputs import EnglishCoachResult
from models.transcript import TranscriptData
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
            transcript=json.dumps([s.model_dump() for s in context.transcript.transcript], indent=2),
            qa_pairs=json.dumps(qa_pairs, indent=2) if qa_pairs else "[]",
        )
        response = await self._llm.complete_json(
            system=prompt,
            user="Analyze the candidate's spoken English and return structured feedback.",
        )
        parsed = EnglishCoachResult.model_validate(response.parsed)
        return parsed.model_dump()
