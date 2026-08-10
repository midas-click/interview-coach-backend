"""Entrypoint for the SQS consumer worker process.

Usage::

    DATABASE_URL=... SQS_QUEUE_URL=... python -m scripts.sqs_consumer
"""

from __future__ import annotations

import asyncio
import contextlib
import sys

from common.config import get_settings
from common.logging import setup_logging
from services.sqs_consumer import SQSConsumer


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    if not settings.sqs_queue_url:
        print("SQS_QUEUE_URL is not set — nothing to consume.", file=sys.stderr)
        sys.exit(1)

    from orchestration.event_publisher import InngestEventPublisher

    publisher = InngestEventPublisher(settings)
    consumer = SQSConsumer(settings, publisher)

    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(consumer.run_forever())


if __name__ == "__main__":
    main()
