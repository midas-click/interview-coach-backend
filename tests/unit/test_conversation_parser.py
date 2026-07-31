"""Conversation Parser tests."""

import json

import pytest

from models.transcript import TranscriptData
from sdk.agent import AgentContext
from agents.conversation_parser import ConversationParser
from services.prompts import PromptStore
from tests.conftest import FakeLLM, sample_transcript


def canned_parse() -> dict:
    return {
        "questions": [
            {"id": "q1", "sequence": 1, "text": "Tell me about yourself.", "speaker": "Interviewer", "start": 0.0, "end": 3.0},
            {"id": "q2", "sequence": 2, "text": "What is your biggest achievement?", "speaker": "Interviewer", "start": 10.0, "end": 13.0},
        ],
        "answers": [
            {"id": "a1", "question_id": "q1", "sequence": 1, "text": "I have five years of experience.", "speaker": "Candidate", "start": 3.0, "end": 10.0},
            {"id": "a2", "question_id": "q2", "sequence": 2, "text": "Leading the migration to microservices.", "speaker": "Candidate", "start": 13.0, "end": 20.0},
        ],
        "timeline": [
            {"type": "question", "speaker": "Interviewer", "text": "Tell me about yourself.", "start": 0.0, "end": 3.0},
            {"type": "answer", "speaker": "Candidate", "text": "I have five years...", "start": 3.0, "end": 10.0},
        ],
    }


@pytest.fixture
def parser() -> ConversationParser:
    llm = FakeLLM(default=canned_parse())
    return ConversationParser(llm, PromptStore())


async def test_parses_valid_transcript(parser: ConversationParser) -> None:
    data = sample_transcript()
    context = AgentContext(
        interview_id="itv-001",
        transcript=TranscriptData.model_validate(data),
    )
    result = await parser.run(context)
    assert result.status == "success"
    output = result.structured_output
    assert len(output["questions"]) == 2
    assert len(output["answers"]) == 2
    assert len(output["timeline"]) == 2
    assert output["questions"][0]["id"] == "q1"
    assert output["answers"][0]["question_id"] == "q1"
    assert result.prompt_version == "1.0.0"


async def test_prompt_version_tracked(parser: ConversationParser) -> None:
    data = sample_transcript()
    context = AgentContext(
        interview_id="itv-001",
        transcript=TranscriptData.model_validate(data),
    )
    result = await parser.run(context)
    assert result.prompt_version == "1.0.0"
