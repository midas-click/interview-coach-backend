"""Transcript schema validation tests."""

import pytest
from pydantic import ValidationError

from models.transcript import TranscriptData
from tests.conftest import sample_transcript


def test_parses_valid_payload() -> None:
    transcript = TranscriptData.model_validate(sample_transcript())
    assert transcript.interview_id == "itv-001"
    assert transcript.company_name == "Acme Corp"
    assert len(transcript.utterances) == 2
    assert transcript.utterances[0].start == 0.0
    assert transcript.utterances[0].end == 3.0


def test_requires_at_least_one_segment() -> None:
    with pytest.raises(ValidationError):
        TranscriptData.model_validate(sample_transcript(utterances=[]))


def test_swaps_end_before_start() -> None:
    """Backward timestamps are silently swapped instead of rejected."""
    data = sample_transcript()
    data["utterances"][0]["endMs"] = 0   # before startMs
    data["utterances"][0]["startMs"] = 3000
    instance = TranscriptData.model_validate(data)
    assert instance.utterances[0].start <= instance.utterances[0].end


def test_ignores_unknown_fields() -> None:
    data = sample_transcript()
    data["extra"] = "ignored"
    data["utterances"][0]["future"] = True
    transcript = TranscriptData.model_validate(data)
    assert transcript.interview_id == "itv-001"
