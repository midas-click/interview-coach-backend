"""Publishes events to Inngest from outside the workflow (SQS consumer).

The ``is_production`` flag controls SDK mode:
  dev → ``INNGEST_DEV=true``, event key ``"local"``, sends to the dev server.
  cloud → signing key / event key from env, sends to Inngest Cloud.
"""

from __future__ import annotations

import inngest

from common.config import Settings
from common.logging import get_logger

logger = get_logger("inngest.event_publisher")


class InngestEventPublisher:
    """Wraps the Inngest Python client so the SQS consumer never touches AI logic."""

    def __init__(self, settings: Settings) -> None:
        self._client = inngest.Inngest(
            app_id="interview-intelligence",
            event_key=settings.inngest_event_key,
            signing_key=settings.inngest_signing_key,
            api_base_url=settings.inngest_api_base_url or None,
            event_api_base_url=settings.inngest_event_api_base_url or None,
            is_production=not settings.inngest_dev,
        )

    def publish_interview_uploaded(
        self, *, interview_id: str, bucket: str, object_key: str
    ) -> None:
        event = inngest.Event(
            name="interview/uploaded",
            data={
                "interview_id": interview_id,
                "bucket": bucket,
                "object_key": object_key,
            },
        )
        ids = self._client.send(event)
        logger.info(
            "published interview/uploaded",
            extra={
                "interview_id": interview_id,
                "inngest_event_ids": ids,
            },
        )
