"""Inngest client factory — builds the SDK client from Settings."""

import inngest

from common.config import Settings


def build_inngest_client(settings: Settings) -> inngest.Inngest:
    """Return a configured Inngest client.

    Dev mode → ``INNGEST_DEV=true``, event key ``"local"``, no signing key needed.
    Cloud mode → reads ``INNGEST_EVENT_KEY`` and ``INNGEST_SIGNING_KEY`` from env.
    """
    return inngest.Inngest(
        app_id="interview-intelligence",
        is_production=not settings.inngest_dev,
        event_key=settings.inngest_event_key,
        signing_key=settings.inngest_signing_key,
        api_base_url=settings.inngest_api_base_url or None,
        event_api_base_url=settings.inngest_event_api_base_url or None,
    )
