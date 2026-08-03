"""Conversation Parser — splits raw transcript into structured Q/A pairs.

Processes transcripts in 15-segment batches with 2-segment overlap for context.
"""

from __future__ import annotations

import json

from models.agent_outputs import ConversationParseResult
from sdk.agent import AgentContext, BaseAgent

BATCH_SIZE = 15
OVERLAP = 2


class ConversationParser(BaseAgent):
    """Parses a raw interview transcript into questions and answers."""

    name = "conversation_parser"
    prompt_name = "conversation_parser"

    async def _execute(self, context: AgentContext) -> dict:
        segments = [s.model_dump() for s in context.transcript.transcript]

        if len(segments) <= BATCH_SIZE:
            return await self._parse_batch(context, segments)

        all_qs: list[dict] = []
        all_as: list[dict] = []
        seen_q_ids: set[str] = set()

        for batch in self._chunk_segments(segments, BATCH_SIZE, OVERLAP):
            result = await self._parse_batch(context, batch)
            for q in result.get("questions", []):
                qid = q["id"]
                if qid not in seen_q_ids:
                    seen_q_ids.add(qid)
                    q["sequence"] = len(all_qs) + 1
                    all_qs.append(q)
            for a in result.get("answers", []):
                a["sequence"] = len(all_as) + 1
                all_as.append(a)

        return {"questions": all_qs, "answers": all_as}

    async def _parse_batch(self, context: AgentContext, segments: list[dict]) -> dict:
        prompt = self._prompts.render(
            self.prompt_name,
            interview_id=context.interview_id,
            language=context.transcript.language,
            transcript=json.dumps(segments, indent=2),
        )
        response = await self._llm.complete_json(
            system=prompt,
            user="Parse this interview transcript into structured questions and answers.",
            max_tokens=4096,
        )
        return ConversationParseResult.model_validate(response.parsed).model_dump()
