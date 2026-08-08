"""English Coach tests."""

import pytest

from models.transcript import TranscriptData
from sdk.agent import AgentContext
from agents.english_coach import EnglishCoach
from services.prompts import PromptStore
from tests.conftest import FakeLLM, sample_transcript


def canned_english() -> dict:
    return {
        "metrics": {
            "grammar": 7.0,
            "naturalness": 6.0,
            "professional_wording": 6.5,
            "fluency": 5.5,
            "conciseness": 6.0,
        },
        "mistakes": [
            {
                "original": "I didn't knew that.",
                "improved": "I didn't know that.",
                "explanation": "Base form after auxiliary 'did'.",
                "alternative": "I wasn't aware of that.",
            }
        ],
        "summary": "Decent grammar but needs fluency improvement.",
    }


@pytest.fixture
def coach() -> EnglishCoach:
    return EnglishCoach(FakeLLM(default=canned_english()), PromptStore())


async def test_analyzes_english(coach: EnglishCoach) -> None:
    context = AgentContext(
        interview_id="itv-001",
        transcript=TranscriptData.model_validate(sample_transcript()),
    )
    result = await coach.run(context)
    assert result.status == "success"
    output = result.structured_output
    assert output["metrics"]["grammar"] == 7.0
    assert len(output["mistakes"]) == 1
    assert output["mistakes"][0]["original"] == "I didn't knew that."


async def test_batches_long_transcripts(coach: EnglishCoach) -> None:
    """Long candidate speech is processed in batches and merged."""
    segments = [
        {"speaker": "Candidate", "start": i, "end": i + 1, "text": f"Segment {i}"}
        for i in range(150)  # > BATCH_SIZE (100) → 2 batch calls + 1 merge call
    ]
    context = AgentContext(
        interview_id="itv-001",
        transcript=TranscriptData.model_validate(sample_transcript(utterances=segments)),
    )
    result = await coach.run(context)
    assert result.status == "success"
    output = result.structured_output
    assert len(output["mistakes"]) == 2  # one mistake per batch, concatenated
    assert output["metrics"]["grammar"] == 7.0  # weighted average unchanged
    assert output["summary"] == "Decent grammar but needs fluency improvement."
