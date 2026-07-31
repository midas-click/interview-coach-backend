"""Agent SDK tests: registry, result envelope, failure capture."""

import pytest

from models.transcript import TranscriptData
from sdk.agent import AgentContext, AgentRegistry, AgentStatus, BaseAgent
from tests.conftest import FakeLLM, sample_transcript


class EchoAgent(BaseAgent):
    name = "echo"

    async def _execute(self, context: AgentContext) -> dict:
        return {"interview_id": context.interview_id, "n": len(context.transcript.transcript)}


class FailingAgent(BaseAgent):
    name = "failing"

    async def _execute(self, context: AgentContext) -> dict:
        raise RuntimeError("boom")


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def context() -> AgentContext:
    return AgentContext(
        interview_id="itv-001",
        transcript=TranscriptData.model_validate(sample_transcript()),
    )


async def test_success_result(llm: FakeLLM, context: AgentContext) -> None:
    result = await EchoAgent(llm).run(context)
    assert result.status == AgentStatus.SUCCESS
    assert result.execution_time >= 0
    assert result.model == "fake-model"
    assert result.structured_output == {"interview_id": "itv-001", "n": 2}


async def test_captures_failure(llm: FakeLLM, context: AgentContext) -> None:
    result = await FailingAgent(llm).run(context)
    assert result.status == AgentStatus.FAILED
    assert "boom" in (result.error or "")
    assert result.execution_time >= 0


def test_registry(llm: FakeLLM) -> None:
    registry = AgentRegistry()
    registry.register("echo", lambda: EchoAgent(llm))
    agent = registry.create("echo")
    assert isinstance(agent, EchoAgent)
    assert registry.names() == ["echo"]

    with pytest.raises(ValueError):
        registry.register("echo", lambda: EchoAgent(llm))

    with pytest.raises(KeyError):
        registry.create("nope")
