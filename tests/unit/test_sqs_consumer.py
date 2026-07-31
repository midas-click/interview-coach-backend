"""SQS consumer tests (EventBridge parsing, consumer logic)."""

import pytest

from services.sqs_consumer import parse_eventbridge_s3_event


def _event_message(**overrides: object) -> str:
    import json
    data: dict = {
        "version": "0",
        "id": "evt-001",
        "detail-type": "Object Created",
        "source": "aws.s3",
        "account": "123456789012",
        "time": "2025-01-01T00:00:00Z",
        "region": "us-east-1",
        "resources": ["arn:aws:s3:::my-bucket"],
        "detail": {
            "version": "0",
            "bucket": {"name": "my-bucket"},
            "object": {"key": "interviews/itv-001/transcript.json", "size": 1024, "etag": "abc"},
        },
    }
    data.update(overrides)  # type: ignore[arg-type]
    return json.dumps(data)


def test_parses_valid_s3_event() -> None:
    parsed = parse_eventbridge_s3_event(_event_message())
    assert parsed == {"interview_id": "itv-001", "bucket": "my-bucket", "object_key": "interviews/itv-001/transcript.json"}


def test_rejects_non_json() -> None:
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_eventbridge_s3_event("not json")


def test_rejects_non_object() -> None:
    with pytest.raises(ValueError, match="not a JSON object"):
        parse_eventbridge_s3_event("[]")


def test_rejects_wrong_source() -> None:
    with pytest.raises(ValueError, match="unexpected event source"):
        parse_eventbridge_s3_event(_event_message(source="aws.ecs"))


def test_rejects_missing_bucket() -> None:
    with pytest.raises(ValueError, match="missing bucket.name"):
        msg = _event_message()
        import json
        data = json.loads(msg)
        del data["detail"]["bucket"]
        parse_eventbridge_s3_event(json.dumps(data))


def test_rejects_missing_object_key() -> None:
    with pytest.raises(ValueError, match="missing object.key"):
        msg = _event_message()
        import json
        data = json.loads(msg)
        del data["detail"]["object"]
        parse_eventbridge_s3_event(json.dumps(data))


def test_rejects_invalid_key_pattern() -> None:
    with pytest.raises(ValueError, match="object key does not match"):
        msg = _event_message()
        import json
        data = json.loads(msg)
        data["detail"]["object"]["key"] = "other/transcript.json"
        parse_eventbridge_s3_event(json.dumps(data))
