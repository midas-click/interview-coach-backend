"""API response schemas shared by routers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from models.agent_outputs import (
    EnglishCoachResult,
    InterviewCoachResult,
    MetricsResult,
    RecommendationResult,
    VocabularyPhrase,
)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: str
    username: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserOut


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"


class UserUpdate(BaseModel):
    username: str
    role: str
    password: str | None = None


class InterviewSummary(BaseModel):
    id: str
    interview_id: str
    company_name: str | None = None
    interview_stage: str | None = None
    language: str
    status: str
    created_at: datetime
    updated_at: datetime


class InterviewDetail(InterviewSummary):
    transcript_segments: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    answers: list[dict[str, Any]] = []
    timeline: list[dict[str, Any]] | None = None


class InterviewListResponse(BaseModel):
    items: list[InterviewSummary]
    total: int
    limit: int
    offset: int


class AnalysisResponse(BaseModel):
    interview_id: str
    analysis: InterviewCoachResult | None = None


class EnglishResponse(BaseModel):
    interview_id: str
    english: EnglishCoachResult | None = None


class VocabularyResponse(BaseModel):
    interview_id: str
    phrases: list[VocabularyPhrase] = []


class MetricsResponse(BaseModel):
    interview_id: str
    metrics: MetricsResult | None = None


class RecommendationResponse(BaseModel):
    interview_id: str
    recommendation: RecommendationResult | None = None


class QuestionReviewsResponse(BaseModel):
    interview_id: str
    reviews: list[dict] = []


class TranscriptCorrectionsResponse(BaseModel):
    interview_id: str
    corrections: list[dict] = []
    corrected_transcript: list[dict] = []
