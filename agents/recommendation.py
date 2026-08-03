"""Recommendation Agent — synthesizes all agent outputs into a learning plan."""

from __future__ import annotations

import json

from models.agent_outputs import RecommendationResult
from sdk.agent import AgentContext, BaseAgent


class RecommendationAgent(BaseAgent):
    """Reads outputs from all previous agents and generates strengths,
    weaknesses, and a personalized learning plan."""

    name = "recommendation"
    prompt_name = "recommendation"

    async def _execute(self, context: AgentContext) -> dict:
        prev = context.previous_outputs
        prompt = self._prompts.render(
            self.prompt_name,
            interview_id=context.interview_id,
            interview_analysis=json.dumps(prev.get("interview_coach"), indent=2),
            english_analysis=json.dumps(prev.get("english_coach"), indent=2),
            vocabulary=json.dumps(prev.get("vocabulary"), indent=2),
            metrics=json.dumps(prev.get("metrics"), indent=2),
        )
        response = await self._llm.complete_json(
            system=prompt,
            user="Generate a personalized learning plan based on the interview analysis above.",
            max_tokens=4096,
        )
        parsed = RecommendationResult.model_validate(response.parsed)
        return parsed.model_dump()
