"""AWS Lambda entrypoint for the S3 → Inngest bridge.

Triggered directly by an EventBridge rule (S3 ``ObjectCreated``). The old ECS
long-polling worker is gone — AWS invokes this Lambda once per event and the
EventBridge retry policy handles transient failures.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from api.lambda_runtime import hydrate_env_from_secrets
from common.config import get_settings
from common.logging import get_logger, setup_logging
from orchestration.event_publisher import InngestEventPublisher
from services.sqs_consumer import parse_eventbridge_s3_event

logger = get_logger("api.worker_handler")

hydrate_env_from_secrets()


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Convert an EventBridge S3 event into an ``interview/uploaded`` event."""
    settings = get_settings()
    setup_logging(settings.log_level)

    try:
        parsed = parse_eventbridge_s3_event(json.dumps(event))
    except ValueError as exc:
        logger.warning("skipping invalid event", extra={"reason": str(exc)})
        return {"statusCode": 200, "processed": False, "reason": str(exc)}

    publisher = InngestEventPublisher(settings)
    asyncio.run(publisher.publish_interview_uploaded(**parsed))
    logger.info("published interview/uploaded", extra=parsed)
    return {"statusCode": 200, "processed": True, **parsed}
