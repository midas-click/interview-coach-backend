"""SQS consumer: polls SQS for EventBridge→S3 events, validates, publishes to Inngest.

The consumer is intentionally lightweight — no AI work, just marshalling.
The ``EventPublisher`` protocol is implemented in ``inngest/`` (Phase 3).
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Protocol

import boto3

from common.config import Settings
from common.logging import get_logger
from services.s3 import parse_interview_object_key

logger = get_logger("services.sqs_consumer")


class EventPublisher(Protocol):
    """Sends interview/uploaded events to Inngest."""

    def publish_interview_uploaded(
        self, *, interview_id: str, bucket: str, object_key: str
    ) -> None:
        ...


# ── EventBridge envelope parsing ────────────────────────────────────────────

def parse_eventbridge_s3_event(message_body: str) -> dict[str, str]:
    """Parse an EventBridge→SQS message and return {bucket, object_key}.

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


# ── Consumer ────────────────────────────────────────────────────────────────

class SQSConsumer:
    """Long-polls an SQS queue and forwards validated events to Inngest."""

    def __init__(
        self,
        settings: Settings,
        publisher: EventPublisher,
        sqs_client: Any = None,
    ) -> None:
        self._queue_url = settings.sqs_queue_url
        self._max_messages = settings.sqs_max_messages
        self._wait_seconds = settings.sqs_wait_time_seconds
        self._visibility_timeout = settings.sqs_visibility_timeout
        self._error_backoff = settings.sqs_poll_error_backoff_seconds
        self._publisher = publisher
        if sqs_client is not None:
            self._sqs = sqs_client
        else:
            session = boto3.Session(
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id or None,
                aws_secret_access_key=settings.aws_secret_access_key or None,
            )
            self._sqs = session.client("sqs")

    async def run_forever(self) -> None:
        """Blocking poll loop with backoff on transport errors."""
        logger.info("sqs consumer started", extra={"queue": self._queue_url})
        while True:
            try:
                count = await self._poll_once()
                if count:
                    logger.debug("sqs batch processed", extra={"count": count})
            except Exception:
                logger.exception("sqs poll error — will retry after backoff")
                await asyncio.sleep(self._error_backoff)

    async def _poll_once(self) -> int:
        messages = await asyncio.to_thread(self._receive_messages)
        processed = 0
        for msg in messages:
            try:
                parsed = parse_eventbridge_s3_event(msg["Body"])
            except ValueError as exc:
                logger.warning(
                    "skipping invalid sqs message",
                    extra={"reason": str(exc), "message_id": msg.get("MessageId")},
                )
                await self._delete(msg["ReceiptHandle"])
                processed += 1
                continue
            try:
                self._publisher.publish_interview_uploaded(**parsed)
            except Exception:
                logger.exception(
                    "failed to publish event — message stays in queue",
                    extra={"interview_id": parsed.get("interview_id")},
                )
                continue  # do not delete; visibility timeout will retry
            await self._delete(msg["ReceiptHandle"])
            processed += 1
            logger.info(
                "published interview/uploaded",
                extra={"interview_id": parsed["interview_id"]},
            )
        return processed

    def _receive_messages(self) -> list[dict[str, Any]]:
        response = self._sqs.receive_message(
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=self._max_messages,
            WaitTimeSeconds=self._wait_seconds,
            VisibilityTimeout=self._visibility_timeout,
            MessageAttributeNames=["All"],
        )
        return response.get("Messages", [])

    async def _delete(self, receipt_handle: str) -> None:
        await asyncio.to_thread(
            self._sqs.delete_message,
            QueueUrl=self._queue_url,
            ReceiptHandle=receipt_handle,
        )
