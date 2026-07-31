"""Vocabulary agent tests."""

import pytest

from models.transcript import TranscriptData
from sdk.agent import AgentContext
from agents.vocabulary import VocabularyAgent
from services.prompts import PromptStore
from tests.conftest import FakeLLM, sample_transcript


def canned_vocab() -> dict:
    return {
        "phrases": [
            {
                "phrase": "Walk me through",
                "meaning": "Explain step by step",
                "example": "Walk me through your debugging process.",
                "difficulty": "intermediate",
                "category": "question",
                "frequency": "common",
            }
        ]
    }


@pytest.fixture
def agent() -> VocabularyAgent:
    return VocabularyAgent(FakeLLM(default=canned_vocab()), PromptStore())


async def test_extracts_phrases(agent: VocabularyAgent) -> None:
    context = AgentContext(
        interview_id="itv-001",
        transcript=TranscriptData.model_validate(sample_transcript()),
    )
    result = await agent.run(context)
    assert result.status == "success"
    output = result.structured_output
    assert len(output["phrases"]) == 1
    assert output["phrases"][0]["phrase"] == "Walk me through"
