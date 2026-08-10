"""Metrics agent tests."""

import pytest

from agents.metrics import MetricsAgent
from models.transcript import TranscriptData
from sdk.agent import AgentContext
from tests.conftest import sample_transcript


@pytest.fixture
def metrics_agent() -> MetricsAgent:
    return MetricsAgent()


async def test_computes_basic_metrics(metrics_agent: MetricsAgent) -> None:
    data = sample_transcript(
        utterances=[
            {"speaker": "Interviewer", "start": 0, "end": 3, "text": "What is your experience?"},
            {"speaker": "Candidate", "start": 3, "end": 10, "text": "I have five years of backend engineering experience."},
            {"speaker": "Interviewer", "start": 10, "end": 12, "text": "Great, tell me more."},
            {"speaker": "Candidate", "start": 12, "end": 18, "text": "I worked primarily with Python and PostgreSQL building microservices."},
        ]
    )
    context = AgentContext(
        interview_id="itv-001",
        transcript=TranscriptData.model_validate(data),
    )
    result = await metrics_agent.run(context)
    assert result.status == "success"
    output = result.structured_output
    assert output["question_count"] == 2
    assert output["answer_count"] == 2
    assert output["words_per_minute"] > 0
    assert output["speaking_ratio"] > 0


async def test_no_candidate_speech(metrics_agent: MetricsAgent) -> None:
    data = sample_transcript(
        utterances=[
            {"speaker": "Interviewer", "start": 0, "end": 3, "text": "Welcome to the interview."},
        ]
    )
    context = AgentContext(
        interview_id="itv-001",
        transcript=TranscriptData.model_validate(data),
    )
    result = await metrics_agent.run(context)
    assert result.status == "success"
    assert result.structured_output["answer_count"] == 0
