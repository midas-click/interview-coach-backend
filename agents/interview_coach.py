"""Interview Coach — evaluates interview quality across 7 dimensions."""

from __future__ import annotations

import json

from models.agent_outputs import InterviewCoachResult
from sdk.agent import AgentContext, BaseAgent


class InterviewCoach(BaseAgent):
    """Scores the candidate across seven dimensions with justifications."""

    name = "interview_coach"
    prompt_name = "interview_coach"

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
            user="Evaluate this interview and return the structured JSON assessment.",
            max_tokens=8192,
        )
        return InterviewCoachResult.model_validate(response.parsed).model_dump()
