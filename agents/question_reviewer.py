"""Question Reviewer — suggests improved answers for each Q&A pair."""

from __future__ import annotations

import json

from models.agent_outputs import QuestionReviewResult
from sdk.agent import AgentContext, BaseAgent


class QuestionReviewer(BaseAgent):
    """Reviews each interview question and suggests a better answer."""

    name = "question_reviewer"
    prompt_name = "question_reviewer"

    async def _execute(self, context: AgentContext) -> dict:
        qa_pairs = context.previous_outputs.get("conversation_parser", {})
        interview_analysis = context.previous_outputs.get("interview_coach", {})

        prompt = self._prompts.render(
            self.prompt_name,
            interview_id=context.interview_id,
            qa_pairs=json.dumps(qa_pairs, indent=2),
            interview_analysis=json.dumps(interview_analysis, indent=2),
        )
        response = await self._llm.complete_json(
            system=prompt,
            user="Review each Q&A pair and suggest improved answers.",
            max_tokens=4096,
        )
        parsed = QuestionReviewResult.model_validate(response.parsed)
        return parsed.model_dump()
