"""Conversation Parser — splits raw transcript into structured Q/A pairs + timeline."""

from __future__ import annotations

import json

from models.agent_outputs import ConversationParseResult
from sdk.agent import AgentContext, BaseAgent


class ConversationParser(BaseAgent):
    """Parses a raw interview transcript into questions, answers, and a timeline."""

    name = "conversation_parser"
    prompt_name = "conversation_parser"

    async def _execute(self, context: AgentContext) -> dict:
        prompt = self._prompts.render(
            self.prompt_name,
            interview_id=context.interview_id,
            language=context.transcript.language,
            transcript=json.dumps(
                [s.model_dump() for s in context.transcript.transcript], indent=2
            ),
        )
        response = await self._llm.complete_json(
            system=prompt,
            user="Parse this interview transcript into structured questions, answers, and timeline.",
            max_tokens=8192,
        )
        parsed = ConversationParseResult.model_validate(response.parsed)
        return parsed.model_dump()
