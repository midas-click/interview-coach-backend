"""Test fakes: scripted LLM, sample transcript, etc."""

from __future__ import annotations

from typing import Any

from sdk.llm import LLMClient, LLMResponse, TokenUsage


class FakeLLM(LLMClient):
    """Scripted LLM: returns canned JSON dicts per call."""

    model = "fake-model"

    def __init__(
        self,
        responses: dict[str, dict[str, Any]] | None = None,
        default: dict[str, Any] | None = None,
        errors: list[Exception] | None = None,
    ) -> None:
        self.responses = responses or {}
        self.default = default or {}
        self.errors = list(errors or [])
        self.calls: list[tuple[str, str]] = []

    async def complete_json(
        self, *, system: str, user: str, max_tokens: int | None = None
    ) -> LLMResponse:
        self.calls.append((system, user))
        if self.errors:
            raise self.errors.pop(0)
        for marker, payload in self.responses.items():
            if marker in user:
                return self._response(payload)
        return self._response(self.default)

    @staticmethod
    def _response(payload: dict[str, Any]) -> LLMResponse:
        return LLMResponse(
            parsed=payload,
            model="fake-model",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=10),
            cost_usd=0.0,
        )


def sample_transcript(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "meetingId": "itv-001",
        "companyName": "Acme Corp",
        "interviewStage": "technical",
        "createdAt": "2025-01-01T10:00:00Z",
        "language": "en",
        "transcript": [
            {"speaker": "Interviewer", "start": 0.0, "end": 3.0, "confidence": 0.9, "text": "Tell me about yourself."},
            {"speaker": "Candidate", "start": 3.0, "end": 9.0, "confidence": 0.8, "text": "I have five years of backend experience."},
        ],
    }
    data.update(overrides)
    return data
