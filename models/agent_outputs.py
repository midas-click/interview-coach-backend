"""Typed structured outputs that agents return and the API exposes."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Conversation Parser ────────────────────────────────────────────────────

class TimelineEntry(BaseModel):
    type: str  # question | answer | other
    speaker: str
    text: str
    start: float
    end: float


class ParsedQuestion(BaseModel):
    id: str
    sequence: int
    text: str
    speaker: str | None = None
    start: float | None = None
    end: float | None = None


class ParsedAnswer(BaseModel):
    id: str
    question_id: str | None = None
    sequence: int
    text: str
    speaker: str | None = None
    start: float | None = None
    end: float | None = None
    duration: float | None = None
    word_count: int | None = None


class ConversationParseResult(BaseModel):
    questions: list[ParsedQuestion] = Field(default_factory=list)
    answers: list[ParsedAnswer] = Field(default_factory=list)
    timeline: list[TimelineEntry] = Field(default_factory=list)


# ── Interview Coach ────────────────────────────────────────────────────────

class DimensionScore(BaseModel):
    score: float
    justification: str


class InterviewCoachResult(BaseModel):
    dimensions: dict[str, DimensionScore]
    overall_score: float
    summary: str


# ── English Coach ──────────────────────────────────────────────────────────

class EnglishMistake(BaseModel):
    original: str
    improved: str
    explanation: str
    alternative: str


class EnglishMetrics(BaseModel):
    grammar: float
    naturalness: float
    professional_wording: float
    fluency: float
    conciseness: float


class EnglishCoachResult(BaseModel):
    metrics: EnglishMetrics
    mistakes: list[EnglishMistake] = Field(default_factory=list)
    summary: str


# ── Vocabulary ─────────────────────────────────────────────────────────────

class VocabularyPhrase(BaseModel):
    phrase: str
    meaning: str
    example: str
    difficulty: str
    category: str
    frequency: str


class VocabularyResult(BaseModel):
    phrases: list[VocabularyPhrase] = Field(default_factory=list)


# ── Metrics (no LLM) ───────────────────────────────────────────────────────

class MetricsResult(BaseModel):
    avg_answer_length: float
    words_per_minute: float
    longest_answer: float
    shortest_answer: float
    speaking_ratio: float
    question_count: int
    answer_count: int
    repeated_words: list[dict] = Field(default_factory=list)
    filler_words: list[dict] = Field(default_factory=list)
    pauses: list[dict] = Field(default_factory=list)


# ── Recommendation ─────────────────────────────────────────────────────────

class StrengthWeakness(BaseModel):
    title: str
    evidence: str
    severity: str | None = None  # only for weaknesses


class LearningPlanWeek(BaseModel):
    week: int
    focus: str
    actions: list[str]


class PracticeExercise(BaseModel):
    exercise: str
    targets: list[str]


class TechnicalTopic(BaseModel):
    topic: str
    priority: str


class RecommendationResult(BaseModel):
    strengths: list[StrengthWeakness] = Field(default_factory=list)
    weaknesses: list[StrengthWeakness] = Field(default_factory=list)
    learning_plan: list[LearningPlanWeek] = Field(default_factory=list)
    english_practice: list[PracticeExercise] = Field(default_factory=list)
    technical_topics: list[TechnicalTopic] = Field(default_factory=list)
    summary: str


# ── Question Reviewer ────────────────────────────────────────────────

class QAReview(BaseModel):
    question_summary: str
    original_answer_summary: str
    recommended_answer: str
    key_improvements: list[str] = Field(default_factory=list)


class QuestionReviewResult(BaseModel):
    reviews: list[QAReview] = Field(default_factory=list)


# ── Transcription Corrector ──────────────────────────────────────────

class MisTranscribedWord(BaseModel):
    original_word: str
    corrected_word: str
    reason: str = ""


class TranscriptCorrection(BaseModel):
    segment_index: int
    original_text: str
    corrected_text: str
    mis_transcribed: list[MisTranscribedWord] = Field(default_factory=list)


class TranscriptionCorrectionResult(BaseModel):
    corrections: list[TranscriptCorrection] = Field(default_factory=list)
