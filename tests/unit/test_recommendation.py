"""Recommendation agent tests."""

import pytest

from models.transcript import TranscriptData
from sdk.agent import AgentContext
from agents.recommendation import RecommendationAgent
from services.prompts import PromptStore
from tests.conftest import FakeLLM, sample_transcript


def canned_rec() -> dict:
    return {
        "strengths": [{"title": "Strong technical answers", "evidence": "Scored 7.5"}],
        "weaknesses": [{"title": "Lacks STAR", "evidence": "Scored 4.0", "severity": "high"}],
        "learning_plan": [
            {"week": 1, "focus": "STAR structure", "actions": ["Practice 3 STAR stories daily"]}
        ],
        "english_practice": [
            {"exercise": "Pause instead of filler words", "targets": ["fluency"]}
        ],
        "technical_topics": [
            {"topic": "System design", "priority": "high"}
        ],
        "summary": "Solid candidate — focus on behavioral interview structure.",
    }


@pytest.fixture
def agent() -> RecommendationAgent:
    return RecommendationAgent(FakeLLM(default=canned_rec()), PromptStore())


async def test_generates_plan(agent: RecommendationAgent) -> None:
    context = AgentContext(
        interview_id="itv-001",
        transcript=TranscriptData.model_validate(sample_transcript()),
        previous_outputs={
            "interview_coach": {"overall_score": 5.8},
            "english_coach": {"metrics": {}},
            "vocabulary": {"phrases": []},
            "metrics": {"avg_answer_length": 15.0},
        },
    )
    result = await agent.run(context)
    assert result.status == "success"
    output = result.structured_output
    assert len(output["strengths"]) == 1
    assert len(output["weaknesses"]) == 1
    assert len(output["learning_plan"]) == 1
    assert output["weaknesses"][0]["severity"] == "high"
