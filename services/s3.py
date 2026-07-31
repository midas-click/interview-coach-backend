"""S3 transcript download service.

The workflow never receives the transcript inside the event; it downloads
it here by bucket + object key.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Protocol

import boto3
from botocore.config import Config
from pydantic import ValidationError

from common.config import Settings
from common.logging import get_logger
from models.transcript import TranscriptData

logger = get_logger("services.s3")

# Desktop app uploads to: interviews/{meeting_id}/transcript.json
OBJECT_KEY_PATTERN = re.compile(r"^interviews/(?P<interview_id>[^/]+)/transcript\.json$")


class TranscriptDownloadError(RuntimeError):
    """Raised when the transcript cannot be downloaded or validated."""


def parse_interview_object_key(object_key: str) -> str | None:
    match = OBJECT_KEY_PATTERN.match(object_key)
    return match.group("interview_id") if match else None


class TranscriptSource(Protocol):
    """Source of raw transcripts (implemented by S3; faked in tests)."""

    async def download(self, bucket: str, object_key: str) -> TranscriptData:
        ...


class S3TranscriptSource:
    """Downloads and validates ``transcript.json`` from S3."""

    def __init__(self, settings: Settings) -> None:
        session = boto3.Session(
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
        )
        self._s3 = session.client(
            "s3", config=Config(retries={"max_attempts": 3, "mode": "standard"})
        )

    async def download(self, bucket: str, object_key: str) -> TranscriptData:
        if not parse_interview_object_key(object_key):
            raise TranscriptDownloadError(
                f"object key must match interviews/<id>/transcript.json, got: {object_key}"
            )
        raw = await asyncio.to_thread(self._get_object, bucket, object_key)
        try:
            payload: Any = json.loads(raw)
            return TranscriptData.model_validate(payload)
        except json.JSONDecodeError as exc:
            raise TranscriptDownloadError(
                f"transcript at {bucket}/{object_key} is not valid JSON"
            ) from exc
        except ValidationError as exc:
            raise TranscriptDownloadError(
                f"transcript at {bucket}/{object_key} failed validation: {exc}"
            ) from exc

    def _get_object(self, bucket: str, object_key: str) -> str:
        response = self._s3.get_object(Bucket=bucket, Key=object_key)
        body = response["Body"].read().decode("utf-8")
        logger.info(
            "transcript downloaded from s3",
            extra={"bucket": bucket, "object_key": object_key, "bytes": len(body)},
        )
        return body
