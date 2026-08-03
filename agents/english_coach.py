"""English Coach — analyzes spoken English. Uses candidate speech only."""

from __future__ import annotations

import json

from models.agent_outputs import EnglishCoachResult
from sdk.agent import AgentContext, BaseAgent


class EnglishCoach(BaseAgent):
    """Analyzes grammar, naturalness, fluency. Feeds only candidate speech to save tokens."""

    name = "english_coach"
    prompt_name = "english_coach"

    async def _execute(self, context: AgentContext) -> dict:
        candidate = self._filter_transcript(context.transcript, "candidate")
        qa_pairs = context.previous_outputs.get("conversation_parser")
        prompt = self._prompts.render(
            self.prompt_name,
            interview_id=context.interview_id,
            transcript=self._transcript_json(candidate),
            qa_pairs=json.dumps(qa_pairs, indent=2) if qa_pairs else "[]",
        )
        response = await self._llm.complete_json(
            system=prompt,
            user="Analyze the candidate's spoken English. Return only the top 15 mistakes.",
            max_tokens=8192,
        )
        return EnglishCoachResult.model_validate(response.parsed).model_dump()
