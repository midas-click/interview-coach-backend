"""Metrics agent — deterministic computation, no LLM.

Computes: average answer length, words per minute, longest/shortest answers,
repeated words, filler words, speaking ratio, question/answer counts.
"""

from __future__ import annotations

from collections import Counter
import re
from typing import Any

from models.agent_outputs import MetricsResult
from sdk.agent import AgentContext, BaseAgent

_FILLER_WORDS = {
    "um", "uh", "er", "ah", "like", "you know", "i mean", "sort of",
    "kind of", "actually", "basically", "literally", "hmm", "right",
    "okay", "so", "well",
}
_WORD_RE = re.compile(r"\b\w+(?:'\w+)?\b")


class MetricsAgent(BaseAgent):
    """Computes quantitative conversation metrics. No LLM required."""

    name = "metrics"

    async def _execute(self, context: AgentContext) -> dict[str, Any]:
        segments = context.transcript.transcript
        text = " ".join(s.text for s in segments)

        # Split into candidate (Me / mic) vs interviewer utterances.
        def _is_candidate(speaker: str) -> bool:
            return speaker.lower() in ("candidate", "me")
        def _is_interviewer(speaker: str) -> bool:
            return speaker.lower() in ("interviewer", "unknown")

        candidate_texts = [s.text for s in segments if _is_candidate(s.speaker)]
        interviewer_texts = [s.text for s in segments if _is_interviewer(s.speaker)]

        # Word counts.
        all_words = _WORD_RE.findall(text.lower())
        total_words = len(all_words) or 1

        # Answer metrics.
        answer_lengths = [len(_WORD_RE.findall(t)) for t in candidate_texts] or [0]
        avg_answer_length = sum(answer_lengths) / len(answer_lengths)

        # Duration.
        total_duration = sum(s.end - s.start for s in segments) or 1
        wpm = total_words / (total_duration / 60)

        # Speaking ratio.
        candidate_duration = sum(s.end - s.start for s in segments if _is_candidate(s.speaker))
        speaking_ratio = candidate_duration / total_duration

        # Filler words.
        filler_counts = {w: text.lower().count(w) for w in _FILLER_WORDS if w in text.lower()}
        filler_list = [{"word": w, "count": c} for w, c in filler_counts.items() if c > 0]

        # Repeated words (top 5 most common, excluding stops).
        _stops = {"the", "a", "an", "is", "was", "are", "were", "be", "been", "i", "you",
                   "he", "she", "it", "we", "they", "me", "him", "her", "us", "them",
                   "my", "your", "his", "its", "our", "their", "and", "or", "but", "in",
                   "on", "at", "to", "for", "of", "with", "that", "this", "from", "by",
                   "do", "does", "did", "have", "has", "had", "not", "no", "yes", "so",
                   "just", "can", "will", "would", "could", "should", "if", "then", "than"}
        content_words = [w for w in all_words if w not in _stops and len(w) > 2]
        word_counts = Counter(content_words)
        repeated = [{"word": w, "count": c} for w, c in word_counts.most_common(5) if c >= 2]

        result = MetricsResult(
            avg_answer_length=round(avg_answer_length, 1),
            words_per_minute=round(wpm, 1),
            longest_answer=float(max(answer_lengths)),
            shortest_answer=float(min(answer_lengths)),
            speaking_ratio=round(speaking_ratio, 2),
            question_count=len(interviewer_texts),
            answer_count=len(candidate_texts),
            repeated_words=repeated,
            filler_words=filler_list,
            pauses=[],  # future feature
        )
        return result.model_dump()
