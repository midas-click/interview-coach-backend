"""Reusable DeepSeek chat client with retries, rate limiting, and cost tracking."""

from __future__ import annotations

import asyncio
import json
import random
import re
import time
from typing import Any

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI

from common.config import Settings
from common.logging import get_logger
from sdk.llm import LLMClient, LLMResponse, TokenUsage

logger = get_logger("services.deepseek")

# USD per 1M tokens (input, output)
_MODEL_PRICING_USD_PER_1M: dict[str, tuple[float, float]] = {
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
}
_DEFAULT_PRICING = (0.27, 1.10)
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class DeepSeekError(RuntimeError):
    """Raised when the DeepSeek API fails after all retries."""


class InvalidJSONError(DeepSeekError):
    """The model's response could not be parsed as a JSON object."""


_JSON_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class RateLimiter:
    """Minimal token-bucket rate limiter for requests-per-second budgets."""

    def __init__(self, rate_per_second: float) -> None:
        self._rate = rate_per_second
        self._tokens = max(rate_per_second, 1.0)
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                self._tokens = min(
                    self._tokens + (now - self._updated) * self._rate, self._rate
                )
                self._updated = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                delay = (1.0 - self._tokens) / self._rate
            await asyncio.sleep(delay)


class DeepSeekClient(LLMClient):
    """JSON-mode client for the DeepSeek API (OpenAI-compatible)."""

    def __init__(self, settings: Settings) -> None:
        if not settings.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is not configured")
        self.model = settings.deepseek_model
        self._max_tokens = settings.deepseek_max_tokens
        self._max_retries = settings.deepseek_max_retries
        self._timeout = settings.deepseek_timeout_seconds
        self._limiter = RateLimiter(settings.deepseek_rpm / 60.0)
        self._client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            timeout=self._timeout,
            max_retries=0,
        )

    async def complete_json(
        self, *, system: str, user: str, max_tokens: int | None = None
    ) -> LLMResponse:
        await self._limiter.acquire()
        for attempt in range(1, self._max_retries + 2):
            try:
                started = time.perf_counter()
                completion = await self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                    max_tokens=max_tokens or self._max_tokens,
                )
                content = completion.choices[0].message.content or ""
                parsed = self._parse_json(content)
                usage = completion.usage
                token_usage = TokenUsage(
                    prompt_tokens=usage.prompt_tokens if usage else 0,
                    completion_tokens=usage.completion_tokens if usage else 0,
                )
                cost = self._estimate_cost(token_usage)
                logger.info(
                    "deepseek call succeeded",
                    extra={
                        "model": self.model,
                        "attempt": attempt,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                        "prompt_tokens": token_usage.prompt_tokens,
                        "completion_tokens": token_usage.completion_tokens,
                        "cost_usd": round(cost, 6),
                    },
                )
                return LLMResponse(
                    parsed=parsed, model=self.model, usage=token_usage, cost_usd=cost
                )
            except Exception as exc:  # noqa: BLE001
                status = self._status_of(exc)
                is_transport_error = isinstance(exc, (APIConnectionError, APITimeoutError))
                is_invalid_json = isinstance(exc, InvalidJSONError)
                if (
                    status not in _RETRYABLE_STATUSES
                    and not is_transport_error
                    and not is_invalid_json
                ) or attempt > self._max_retries:
                    logger.error(
                        "deepseek call failed",
                        extra={
                            "model": self.model,
                            "attempt": attempt,
                            "max_retries": self._max_retries,
                            "error": str(exc),
                        },
                    )
                    raise DeepSeekError(str(exc)) from exc
                delay = (2**attempt) + random.uniform(0, 0.5)
                logger.warning(
                    "deepseek retry scheduled",
                    extra={
                        "model": self.model,
                        "attempt": attempt,
                        "status": status,
                        "retry_in_s": round(delay, 2),
                    },
                )
                await asyncio.sleep(delay)
        # Unreachable — kept for type safety
        raise DeepSeekError("max retries exceeded")

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        candidates = [content]
        extracted = DeepSeekClient._extract_json_object(content)
        if extracted is not None and extracted != content.strip():
            candidates.append(extracted)
        for candidate in candidates:
            try:
                parsed: Any = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed, dict):
                raise InvalidJSONError(
                    f"model returned non-object JSON: {type(parsed).__name__}"
                )
            if candidate is not content:
                logger.warning(
                    "model returned JSON embedded in other text — recovered it",
                    extra={"recovered_chars": len(extracted)},
                )
            return parsed
        # Nothing parsed — report where the best candidate broke.
        best = extracted if extracted is not None else content
        try:
            json.loads(best)
        except json.JSONDecodeError as exc:
            window = best[max(0, exc.pos - 80) : exc.pos + 80]
            raise InvalidJSONError(
                f"model returned invalid JSON at offset {exc.pos}/{len(best)}: …{window}…"
            ) from exc
        raise InvalidJSONError("model returned invalid JSON")

    @staticmethod
    def _extract_json_object(content: str) -> str | None:
        """Pull an outer JSON object out of surrounding text (fences, prose)."""
        text = content.lstrip("\ufeff \t\r\n")
        m = _JSON_CODE_FENCE_RE.search(text)
        if m:
            text = m.group(1).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            return None
        return text[start : end + 1]

    @staticmethod
    def _status_of(exc: Exception) -> int:
        status = getattr(exc, "status_code", None)
        return status if isinstance(status, int) else 0

    def _estimate_cost(self, usage: TokenUsage) -> float:
        input_price, output_price = _MODEL_PRICING_USD_PER_1M.get(
            self.model, _DEFAULT_PRICING
        )
        return (
            usage.prompt_tokens * input_price + usage.completion_tokens * output_price
        ) / 1_000_000
