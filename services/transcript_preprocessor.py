"""Transcript pre-processor: merges STT fragments into coherent utterances.

The desktop app's STT engine produces many small, overlapping chunks — each
is an incremental refinement of the same utterance, not a standalone sentence.
This module deduplicates and merges them before agents process the transcript.
"""

from __future__ import annotations

import re

from models.transcript import TranscriptData, TranscriptSegment


def preprocess(transcript: TranscriptData, gap_threshold: float = 1.0) -> TranscriptData:
    """Normalise a raw STT transcript into coherent speaker utterances.

    1. Deduplicate overlapping chunks from the same speaker (keep longest).
    2. Merge consecutive fragments from the same speaker within *gap_threshold*.
    3. Clean trailing punctuation artefacts left by STT splitting.
    """
    segments = transcript.transcript
    if not segments:
        return transcript

    cleaned = _clean_text_artefacts(segments)
    deduped = _deduplicate_overlaps(cleaned)
    merged = _merge_consecutive(deduped, gap_threshold)

    return TranscriptData(
        interview_id=transcript.interview_id,
        company_name=transcript.company_name,
        interview_stage=transcript.interview_stage,
        schema_version=transcript.schema_version,
        transcriber=transcript.transcriber,
        created_at=transcript.created_at,
        language=transcript.language,
        utterances=merged,
    )


# ── internals ──────────────────────────────────────────────────────────────

# STT often leaves trailing connectors / dashes when splitting.
_TRAILING_JUNK_RE = re.compile(r"[-–—]\s*$|(\s+\.\.\.?\s*)$")
_MULTISPACE_RE = re.compile(r"\s{2,}")


def _clean_text_artefacts(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    result: list[TranscriptSegment] = []
    for s in segments:
        text = _TRAILING_JUNK_RE.sub("", s.text).strip()
        text = _MULTISPACE_RE.sub(" ", text)
        if text:
            result.append(
                TranscriptSegment(
                    speaker=s.speaker,
                    start=s.start,
                    end=s.end,
                    confidence=s.confidence,
                    text=text,
                )
            )
    return result


def _deduplicate_overlaps(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    """STT produces multiple refinements with identical *start* times and
    progressively longer *end* times.  Keep only the longest version per
    (speaker, start) bucket."""
    buckets: dict[tuple[str, float], TranscriptSegment] = {}
    for s in segments:
        key = (s.speaker, s.start)
        existing = buckets.get(key)
        if (
            existing is None
            or s.end > existing.end
            or (s.end == existing.end and s.confidence > existing.confidence)
        ):
            buckets[key] = s
    return sorted(buckets.values(), key=lambda s: s.start)


def _merge_consecutive(
    segments: list[TranscriptSegment], gap_threshold: float
) -> list[TranscriptSegment]:
    """Glue together same-speaker fragments separated by <= *gap_threshold* seconds."""
    if not segments:
        return []

    merged: list[TranscriptSegment] = []
    current = segments[0]

    for nxt in segments[1:]:
        if nxt.speaker == current.speaker and (nxt.start - current.end) <= gap_threshold:
            # Absorb this fragment into the current utterance.
            merged_text = _merge_text(current.text, nxt.text)
            current = TranscriptSegment(
                speaker=current.speaker,
                start=current.start,
                end=nxt.end,
                confidence=max(current.confidence, nxt.confidence),
                text=merged_text,
            )
        else:
            merged.append(current)
            current = nxt

    merged.append(current)
    return merged


def _merge_text(a: str, b: str) -> str:
    """Join two fragment texts, avoiding obvious duplication."""
    a = a.strip()
    b = b.strip()
    if not a:
        return b
    if not b:
        return a
    # If B is wholly contained in A, skip B.
    if b in a:
        return a
    # If A ends with the beginning of B, overlap-join.
    for i in range(min(len(a), len(b)), 0, -1):
        if a[-i:] == b[:i]:
            return a + b[i:]
    return f"{a} {b}"
