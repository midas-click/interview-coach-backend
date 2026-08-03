"""Conversation Parser — splits raw transcript into structured Q/A pairs."""

from __future__ import annotations

from models.agent_outputs import ConversationParseResult
from sdk.agent import AgentContext, BaseAgent


class ConversationParser(BaseAgent):
    """Parses a raw interview transcript into questions and answers."""

    name = "conversation_parser"
    prompt_name = "conversation_parser"

    async def _execute(self, context: AgentContext) -> dict:
        prompt = self._prompts.render(
            self.prompt_name,
            interview_id=context.interview_id,
            language=context.transcript.language,
            transcript=self._transcript_json(context.transcript),
        )
        response = await self._llm.complete_json(
            system=prompt,
            user="Parse this interview transcript into structured questions and answers.",
            max_tokens=8192,
        )
        return ConversationParseResult.model_validate(response.parsed).model_dump()
