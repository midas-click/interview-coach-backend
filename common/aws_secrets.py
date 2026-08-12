"""AWS Secrets Manager access with process-wide caching.

Lambda has no ``secrets`` block like ECS, so the Lambda entrypoints resolve
secret values from Secrets Manager at cold start (see ``api.lambda_runtime``)
and inject them into ``os.environ`` where pydantic ``Settings`` can read them.

Note: this module must NOT construct ``Settings`` — doing so would cache a
Settings instance before secret hydration, and handlers reading it afterwards
would see stale defaults.
"""

from __future__ import annotations

import os
from functools import lru_cache

import boto3


@lru_cache(maxsize=64)
def get_secret_value(secret_id: str) -> str:
    """Return the ``SecretString`` for ``secret_id`` (ARN or name).

    Raises:
        ValueError: if the secret has no ``SecretString``.
    """
    client = boto3.client(
        "secretsmanager", region_name=os.environ.get("AWS_REGION", "us-east-2")
    )
    response = client.get_secret_value(SecretId=secret_id)
    value = response.get("SecretString")
    if value is None:
        raise ValueError(f"secret {secret_id!r} has no SecretString")
    return value
