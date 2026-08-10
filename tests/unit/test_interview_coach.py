"""Interview Coach tests."""

import pytest

from agents.interview_coach import InterviewCoach
from models.transcript import TranscriptData
from sdk.agent import AgentContext
from services.prompts import PromptStore
from tests.conftest import FakeLLM, sample_transcript


def canned_coach() -> dict:
    return {
        "dimensions": {
            "technical_quality": {"score": 7.5, "justification": "Good depth."},
            "communication": {"score": 6.0, "justification": "Clear but brief."},
            "confidence": {"score": 5.5, "justification": "Some hesitation."},
            "star": {"score": 4.0, "justification": "Missing structure."},
            "ownership": {"score": 6.5, "justification": "Shows initiative."},
            "clarity": {"score": 6.0, "justification": "Easy to follow."},
            "completeness": {"score": 5.0, "justification": "Could elaborate."},
        },
        "overall_score": 5.8,
        "summary": "Solid technical foundation but needs improvement in structured responses.",
    }


@pytest.fixture
def coach() -> InterviewCoach:
    return InterviewCoach(FakeLLM(default=canned_coach()), PromptStore())


async def test_evaluates_dimensions(coach: InterviewCoach) -> None:
    context = AgentContext(
        interview_id="itv-001",
        transcript=TranscriptData.model_validate(sample_transcript()),
        previous_outputs={"conversation_parser": {"questions": [], "answers": []}},
    )
    result = await coach.run(context)
    assert result.status == "success"
    output = result.structured_output
    assert output["overall_score"] == 5.8
    assert set(output["dimensions"]) == {
        "technical_quality", "communication", "confidence",
        "star", "ownership", "clarity", "completeness",
    }
