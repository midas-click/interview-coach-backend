"""Worker Lambda handler tests (EventBridge → Inngest bridge)."""

from __future__ import annotations

from typing import Any

import pytest

from api import worker_handler


def _event() -> dict[str, Any]:
    return {
        "version": "0",
        "id": "evt-001",
        "detail-type": "Object Created",
        "source": "aws.s3",
        "account": "123456789012",
        "time": "2025-01-01T00:00:00Z",
        "region": "us-east-2",
        "resources": ["arn:aws:s3:::my-bucket"],
        "detail": {
            "version": "0",
            "bucket": {"name": "my-bucket"},
            "object": {"key": "interviews/itv-001/transcript.json"},
        },
    }


class _FakePublisher:
    def __init__(self, settings: Any) -> None:
        self.settings = settings
        self.calls: list[dict[str, str]] = []

    async def publish_interview_uploaded(self, **kwargs: str) -> None:
        self.calls.append(kwargs)


@pytest.fixture
def fake_publisher(monkeypatch: pytest.MonkeyPatch) -> _FakePublisher:
    publisher = _FakePublisher(None)

    def factory(settings: Any) -> _FakePublisher:
        publisher.settings = settings
        return publisher

    monkeypatch.setattr(worker_handler, "InngestEventPublisher", factory)
    return publisher


def test_skips_invalid_event(fake_publisher: _FakePublisher) -> None:
    result = worker_handler.handler({"source": "aws.ecs", "detail": {}}, None)
    assert result["processed"] is False
    assert fake_publisher.calls == []


def test_publishes_valid_event(fake_publisher: _FakePublisher) -> None:
    result = worker_handler.handler(_event(), None)
    assert result["processed"] is True
    assert fake_publisher.calls == [
        {
            "interview_id": "itv-001",
            "bucket": "my-bucket",
            "object_key": "interviews/itv-001/transcript.json",
        }
    ]
