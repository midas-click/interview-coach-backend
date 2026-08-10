"""DeepSeek client tests (no network)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from common.config import Settings
from sdk.llm import TokenUsage
from services.deepseek import DeepSeekClient, DeepSeekError


def _client(**overrides: object) -> DeepSeekClient:
    settings = Settings(
        _env_file=None,
        deepseek_api_key="test-key",
        deepseek_rpm=1000,
        **overrides,
    )
    return DeepSeekClient(settings)


def _completion(content: str, prompt_tokens: int = 5, completion_tokens: int = 7) -> object:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


def _async(fn: object) -> object:
    async def wrapper(*_a: object, **_kw: object) -> object:
        return fn()  # type: ignore[operator]
    return wrapper


async def test_requires_api_key() -> None:
    settings = Settings(_env_file=None, deepseek_api_key=None)
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        DeepSeekClient(settings)


async def test_parses_json_and_reports_usage() -> None:
    client = _client()
    client._client.chat.completions.create = _async(lambda: _completion('{"ok": true}'))  # type: ignore[attr-defined]
    response = await client.complete_json(system="s", user="u")
    assert response.parsed == {"ok": True}
    assert response.usage.total == 12
    assert response.cost_usd == pytest.approx((5 * 0.27 + 7 * 1.10) / 1_000_000, rel=1e-6)


async def test_retries_then_succeeds() -> None:
    client = _client(deepseek_max_retries=2)
    attempts = {"n": 0}

    async def flaky(*_a: object, **_kw: object) -> object:
        attempts["n"] += 1
        if attempts["n"] < 2:
            exc = RuntimeError("rate limited")
            exc.status_code = 429  # type: ignore[attr-defined]
            raise exc
        return _completion('{"ok": true}')

    client._client.chat.completions.create = flaky  # type: ignore[attr-defined]
    response = await client.complete_json(system="s", user="u")
    assert response.parsed == {"ok": True}
    assert attempts["n"] == 2


async def test_gives_up_after_max_retries() -> None:
    client = _client(deepseek_max_retries=3)

    async def always_fail(*_a: object, **_kw: object) -> object:
        exc = RuntimeError("boom")
        exc.status_code = 503  # type: ignore[attr-defined]
        raise exc

    client._client.chat.completions.create = always_fail  # type: ignore[attr-defined]
    with pytest.raises(DeepSeekError):
        await client.complete_json(system="s", user="u")


async def test_retries_on_transport_error() -> None:
    """Network-level errors (no HTTP status) should retry, not fail fast."""
    import httpx
    from openai import APIConnectionError

    client = _client(deepseek_max_retries=2)
    attempts = {"n": 0}

    async def flaky(*_a: object, **_kw: object) -> object:
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise APIConnectionError(request=httpx.Request("POST", "https://api.deepseek.com"))
        return _completion('{"ok": true}')

    client._client.chat.completions.create = flaky  # type: ignore[attr-defined]
    response = await client.complete_json(system="s", user="u")
    assert response.parsed == {"ok": True}
    assert attempts["n"] == 2


async def test_no_retry_on_non_retryable() -> None:
    client = _client()
    attempts = {"n": 0}

    async def bad_request(*_a: object, **_kw: object) -> object:
        attempts["n"] += 1
        exc = RuntimeError("bad")
        exc.status_code = 400  # type: ignore[attr-defined]
        raise exc

    client._client.chat.completions.create = bad_request  # type: ignore[attr-defined]
    with pytest.raises(DeepSeekError):
        await client.complete_json(system="s", user="u")
    assert attempts["n"] == 1


async def test_invalid_json_raises_after_retries() -> None:
    """Invalid JSON is retryable; must still give up after max_retries."""
    client = _client(deepseek_max_retries=0)
    client._client.chat.completions.create = _async(lambda: _completion("not json"))  # type: ignore[attr-defined]
    with pytest.raises(DeepSeekError, match="invalid JSON"):
        await client.complete_json(system="s", user="u")


async def test_recovers_json_surrounded_by_text() -> None:
    client = _client()
    client._client.chat.completions.create = _async(  # type: ignore[attr-defined]
        lambda: _completion('Here is your JSON:\n{"ok": true}\nHope that helps.')
    )
    response = await client.complete_json(system="s", user="u")
    assert response.parsed == {"ok": True}


async def test_recovers_json_from_code_fence() -> None:
    client = _client()
    client._client.chat.completions.create = _async(  # type: ignore[attr-defined]
        lambda: _completion('```json\n{"ok": true}\n```')
    )
    response = await client.complete_json(system="s", user="u")
    assert response.parsed == {"ok": True}


async def test_non_object_json_raises() -> None:
    client = _client(deepseek_max_retries=0)
    client._client.chat.completions.create = _async(lambda: _completion('[1, 2, 3]'))  # type: ignore[attr-defined]
    with pytest.raises(DeepSeekError, match="non-object JSON"):
        await client.complete_json(system="s", user="u")


def test_cost_uses_model_pricing() -> None:
    client = _client(deepseek_model="deepseek-chat")
    usage = TokenUsage(prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert client._estimate_cost(usage) == pytest.approx(0.27 + 1.10, rel=1e-6)
