"""Transcript schema validation tests."""

import pytest
from pydantic import ValidationError

from models.transcript import TranscriptData
from tests.conftest import sample_transcript


def test_parses_valid_payload() -> None:
    transcript = TranscriptData.model_validate(sample_transcript())
    assert transcript.meeting_id == "itv-001"
    assert transcript.company_name == "Acme Corp"
    assert len(transcript.transcript) == 2


def test_requires_at_least_one_segment() -> None:
    with pytest.raises(ValidationError):
        TranscriptData.model_validate(sample_transcript(transcript=[]))


def test_swaps_end_before_start() -> None:
    """Backward timestamps are silently swapped instead of rejected."""
    data = sample_transcript()
    data["transcript"][0]["end"] = -1.0
    instance = TranscriptData.model_validate(data)
    assert instance.transcript[0].start <= instance.transcript[0].end


def test_ignores_unknown_fields() -> None:
    data = sample_transcript()
    data["extra"] = "ignored"
    data["transcript"][0]["future"] = True
    transcript = TranscriptData.model_validate(data)
    assert transcript.meeting_id == "itv-001"
