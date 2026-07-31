"""LLM client contract — agents depend only on this interface."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class TokenUsage:
    def __init__(self, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LLMResponse:
    """Normalized result of a JSON-mode chat completion."""

    def __init__(
        self, *, parsed: dict[str, Any], model: str, usage: TokenUsage, cost_usd: float
    ) -> None:
        self.parsed = parsed
        self.model = model
        self.usage = usage
        self.cost_usd = cost_usd

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"LLMResponse(model={self.model!r}, tokens={self.usage.total}, "
            f"cost_usd={self.cost_usd:.4f})"
        )


@runtime_checkable
class LLMClient(Protocol):
    """Chat-completion client in JSON mode (implemented by DeepSeekClient)."""

    model: str

    async def complete_json(
        self, *, system: str, user: str, max_tokens: int | None = None
    ) -> LLMResponse:
        ...
