"""AWS Lambda entrypoint for running database migrations at deploy time.

Invoked from CI/CD after the API Lambda is deployed::

    aws lambda invoke --function-name <name>-migrate --payload '{}' out.json
"""

from __future__ import annotations

from typing import Any

from api.lambda_runtime import hydrate_env_from_secrets
from common.config import get_settings
from common.logging import setup_logging
from database.migrate import run_migrations


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    hydrate_env_from_secrets()
    settings = get_settings()
    setup_logging(settings.log_level)
    run_migrations(settings.database_url)
    return {"statusCode": 200, "body": "migrations applied"}
