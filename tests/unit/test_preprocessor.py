"""Transcript pre-processor tests."""

from models.transcript import TranscriptData, TranscriptSegment
from services.transcript_preprocessor import (
    _clean_text_artefacts,
    _deduplicate_overlaps,
    _merge_consecutive,
    _merge_text,
    preprocess,
)


def sample_transcript(**kw) -> TranscriptData:
    return TranscriptData(
        meeting_id="t1", language="en",
        transcript=[
            TranscriptSegment(speaker="Interviewer", start=0.0, end=2.0, text="Hello, welcome."),
            TranscriptSegment(speaker="Interviewer", start=0.0, end=3.5, text="Hello, welcome to the interview."),
            TranscriptSegment(speaker="Candidate", start=3.5, end=4.0, text="Thank"),
            TranscriptSegment(speaker="Candidate", start=4.2, end=5.0, text="you."),
            TranscriptSegment(speaker="Candidate", start=5.5, end=10.0, text="I'm happy to be here."),
        ],
        **kw,
    )


def test_deduplicate_overlaps() -> None:
    segs = [
        TranscriptSegment(speaker="A", start=0, end=2, text="Hello."),
        TranscriptSegment(speaker="A", start=0, end=5, text="Hello, welcome to the interview."),
        TranscriptSegment(speaker="B", start=5, end=7, text="Thanks."),
    ]
    result = _deduplicate_overlaps(segs)
    assert len(result) == 2
    assert result[0].end == 5.0  # kept longer version
    assert result[0].text == "Hello, welcome to the interview."


def test_merge_consecutive() -> None:
    segs = [
        TranscriptSegment(speaker="A", start=0, end=1, text="I think"),
        TranscriptSegment(speaker="A", start=1.5, end=3, text="that's correct."),
        TranscriptSegment(speaker="B", start=4, end=5, text="Yes."),
    ]
    result = _merge_consecutive(segs, gap_threshold=1.0)
    assert len(result) == 2  # A's two fragments merged, B separate
    assert result[0].text == "I think that's correct."


def test_merge_text_overlap() -> None:
    assert _merge_text("I think that", "that's correct.") == "I think that's correct."
    assert _merge_text("Hello", "Hello world") == "Hello world"


def test_merge_text_contained() -> None:
    assert _merge_text("Hello world", "world") == "Hello world"


def test_clean_trailing_dash() -> None:
    segs = [
        TranscriptSegment(speaker="A", start=0, end=1, text="I was going to-"),
        TranscriptSegment(speaker="B", start=1, end=2, text="Yes."),
    ]
    cleaned = _clean_text_artefacts(segs)
    assert cleaned[0].text == "I was going to"


def test_full_pipeline() -> None:
    # Simulate the STT chunking pattern the user described.
    data = TranscriptData(
        meeting_id="t1", language="en",
        transcript=[
            # Overlapping refinements (same start time)
            TranscriptSegment(speaker="A", start=12.35, end=14.12, text="Hi, Thank you for joining."),
            TranscriptSegment(speaker="A", start=12.35, end=15.18, text="The solution that we provide is our track."),
            TranscriptSegment(speaker="A", start=12.35, end=15.98, text="This is our track management for ..."),
            TranscriptSegment(speaker="A", start=12.35, end=18.18, text="For customers."),
            TranscriptSegment(speaker="A", start=12.35, end=24.9, text="For customers and our clients, we provide support for over 30-package formats."),

            # Short gap → merge
            TranscriptSegment(speaker="A", start=29.7, end=32.96, text="That kind of comes with it."),
            TranscriptSegment(speaker="A", start=33.0, end=35.0, text="We support all the major ecosystems."),
        ],
    )
    result = preprocess(data, gap_threshold=1.0)
    # Overlaps deduplicated: only 1 segment from the 12.35 bucket (longest + highest confidence)
    # Consecutive A segments merged: 29.7–32.96 + 33.0–35.0 → 29.7–35.0
    assert len(result.transcript) <= 3
