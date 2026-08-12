"""EventBridge S3 event parsing.

Used by the worker Lambda (``api.worker_handler``) to translate an
S3 ``ObjectCreated`` event into ``{interview_id, bucket, object_key}``.

The old ECS long-polling ``SQSConsumer`` is gone — AWS now invokes the worker
Lambda directly and the EventBridge rule's retry policy handles failures.
"""

from __future__ import annotations

import json
from typing import Any

from services.s3 import parse_interview_object_key


def parse_eventbridge_s3_event(message_body: str) -> dict[str, str]:
    """Parse an EventBridge S3 event (as JSON text) and return
    ``{interview_id, bucket, object_key}``.

    Raises ValueError if the message is not a valid S3 ObjectCreated event.
    """
    try:
        envelope = json.loads(message_body)
    except json.JSONDecodeError as exc:
        raise ValueError("message body is not valid JSON") from exc

    if not isinstance(envelope, dict):
        raise ValueError("message body is not a JSON object")

    source = str(envelope.get("source", ""))
    if source != "aws.s3":
        raise ValueError(f"unexpected event source: {source!r}")

    detail: dict[str, Any] = envelope.get("detail") or {}
    bucket = str(detail.get("bucket", {}).get("name", ""))
    if not bucket:
        raise ValueError("event detail missing bucket.name")

    object_key = str(detail.get("object", {}).get("key", ""))
    if not object_key:
        raise ValueError("event detail missing object.key")

    interview_id = parse_interview_object_key(object_key)
    if not interview_id:
        raise ValueError(
            f"object key does not match interviews/<id>/transcript.json: {object_key}"
        )

    return {"interview_id": interview_id, "bucket": bucket, "object_key": object_key}
