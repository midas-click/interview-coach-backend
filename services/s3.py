"""S3 transcript download service.

The workflow never receives the transcript inside the event; it downloads
it here by bucket + object key.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
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
        # Let boto3 resolve credentials from the environment. On Lambda the
        # runtime injects AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY/AWS_SESSION_TOKEN;
        # passing the first two explicitly would DROP the session token and
        # break every request with InvalidAccessKeyId.
        session = boto3.Session(region_name=settings.aws_region)
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


class DevTranscriptSource:
    """Reads transcript.json from the local filesystem for development.

    Looks for files at ``data/transcripts/{interview_id}.json``.
    No AWS credentials needed — bypasses the S3→EventBridge→SQS chain.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or Path("data/transcripts")
        self._data_dir.mkdir(parents=True, exist_ok=True)

    async def download(self, bucket: str, object_key: str) -> TranscriptData:
        interview_id = parse_interview_object_key(object_key)
        if not interview_id:
            raise TranscriptDownloadError(
                f"object key must match interviews/<id>/transcript.json, got: {object_key}"
            )
        file_path = self._data_dir / f"{interview_id}.json"
        if not file_path.exists():
            raise TranscriptDownloadError(
                f"transcript not found: {file_path} — place a transcript.json there or set "
                f"the file path in data/transcripts/{interview_id}.json"
            )
        try:
            raw = file_path.read_text(encoding="utf-8")
            payload: Any = json.loads(raw)
            logger.info(
                "transcript loaded from local disk",
                extra={"interview_id": interview_id, "path": str(file_path)},
            )
            return TranscriptData.model_validate(payload)
        except json.JSONDecodeError as exc:
            raise TranscriptDownloadError(f"invalid JSON in {file_path}") from exc
        except ValidationError as exc:
            raise TranscriptDownloadError(f"transcript validation failed: {exc}") from exc
