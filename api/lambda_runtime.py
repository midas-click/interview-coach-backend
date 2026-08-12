"""Shared runtime bootstrap for AWS Lambda entrypoints.

AWS Lambda environment variables cannot reference Secrets Manager values the
way ECS ``secrets`` blocks do, so secret values are resolved at cold start and
injected into ``os.environ`` before ``Settings`` is constructed. Lookups are
cached for the lifetime of the execution environment.
"""

from __future__ import annotations

import os

from common.aws_secrets import get_secret_value

# Maps a pydantic ``Settings`` env var → the plain (non-secret) env var that
# holds the Secrets Manager ARN for it.
_SECRET_MAP: dict[str, str] = {
    "DATABASE_URL": "SECRET_DATABASE_URL_ARN",
    "DEEPSEEK_API_KEY": "SECRET_DEEPSEEK_API_KEY_ARN",
    "INNGEST_EVENT_KEY": "SECRET_INNGEST_EVENT_KEY_ARN",
    "INNGEST_SIGNING_KEY": "SECRET_INNGEST_SIGNING_KEY_ARN",
    "JWT_SECRET_KEY": "SECRET_JWT_SECRET_KEY_ARN",
}


def hydrate_env_from_secrets() -> None:
    """Populate ``os.environ`` with secret values. Explicit env vars win."""
    for name, arn_var in _SECRET_MAP.items():
        arn = os.environ.get(arn_var)
        if arn and name not in os.environ:
            os.environ[name] = get_secret_value(arn)
