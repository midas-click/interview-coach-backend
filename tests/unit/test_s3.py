"""S3 service tests (key parsing, fake download)."""

import pytest

from models.transcript import TranscriptData
from services.s3 import parse_interview_object_key


def test_parse_valid_key() -> None:
    assert parse_interview_object_key("interviews/abc123/transcript.json") == "abc123"


def test_parse_key_with_path_prefix() -> None:
    assert parse_interview_object_key("interviews/my.uuid-v2/transcript.json") == "my.uuid-v2"


def test_parse_rejects_wrong_prefix() -> None:
    assert parse_interview_object_key("other/abc123/transcript.json") is None


def test_parse_rejects_wrong_extension() -> None:
    assert parse_interview_object_key("interviews/abc123/transcript.txt") is None


def test_parse_rejects_extra_segments() -> None:
    assert parse_interview_object_key("interviews/a/b/transcript.json") is None
