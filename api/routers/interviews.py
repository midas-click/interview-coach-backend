"""REST endpoints for interview data."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_analysis_repo, get_interview_repo
from models.api import (
    AnalysisResponse,
    EnglishResponse,
    InterviewDetail,
    InterviewSummary,
    MetricsResponse,
    RecommendationResponse,
    VocabularyResponse,
)
from models.agent_outputs import VocabularyPhrase
from repositories.analyses import AnalysisRepository
from repositories.interviews import InterviewRepository

router = APIRouter(prefix="/interviews", tags=["interviews"])


def _summary(row: Any) -> InterviewSummary:
    return InterviewSummary(
        id=str(row.id),
        interview_id=row.interview_id,
        company_name=row.company_name,
        interview_stage=row.interview_stage,
        language=row.language,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[InterviewSummary])
def list_interviews(
    limit: int = 50,
    offset: int = 0,
    repo: InterviewRepository = Depends(get_interview_repo),
) -> list[InterviewSummary]:
    return [_summary(r) for r in repo.list(limit=limit, offset=offset)]


@router.get("/{interview_id}", response_model=InterviewDetail)
def get_interview(
    interview_id: str,
    repo: InterviewRepository = Depends(get_interview_repo),
) -> InterviewDetail:
    interview = repo.get(interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="interview not found")
    transcript = repo.get_transcript(interview_id)
    questions = repo.get_questions(interview_id)
    answers = repo.get_answers(interview_id)
    return InterviewDetail(
        id=str(interview.id),
        interview_id=interview.interview_id,
        company_name=interview.company_name,
        interview_stage=interview.interview_stage,
        language=interview.language,
        status=interview.status,
        created_at=interview.created_at,
        updated_at=interview.updated_at,
        transcript_segments=transcript.raw_json.get("transcript", []) if transcript else [],
        questions=[
            {
                "id": str(q.id),
                "sequence": q.sequence,
                "text": q.text,
                "speaker": q.speaker,
                "start": q.start_time,
                "end": q.end_time,
            }
            for q in questions
        ],
        answers=[
            {
                "id": str(a.id),
                "sequence": a.sequence,
                "text": a.text,
                "speaker": a.speaker,
                "start": a.start_time,
                "end": a.end_time,
                "duration": a.duration,
                "word_count": a.word_count,
            }
            for a in answers
        ],
        timeline=transcript.parsed_timeline if transcript else None,
    )


@router.get("/{interview_id}/analysis", response_model=AnalysisResponse)
def get_analysis(
    interview_id: str,
    repo: AnalysisRepository = Depends(get_analysis_repo),
) -> AnalysisResponse:
    row = repo.get_interview_analysis(interview_id)
    if not row:
        return AnalysisResponse(interview_id=interview_id, analysis=None)
    return AnalysisResponse(
        interview_id=interview_id,
        analysis={
            "dimensions": row.dimensions,
            "overall_score": row.overall_score,
            "summary": row.summary,
        },
    )


@router.get("/{interview_id}/english", response_model=EnglishResponse)
def get_english(
    interview_id: str,
    repo: AnalysisRepository = Depends(get_analysis_repo),
) -> EnglishResponse:
    row = repo.get_english_analysis(interview_id)
    if not row:
        return EnglishResponse(interview_id=interview_id, english=None)
    return EnglishResponse(
        interview_id=interview_id,
        english={
            "metrics": row.metrics,
            "mistakes": row.mistakes,
            "summary": row.summary,
        },
    )


@router.get("/{interview_id}/vocabulary", response_model=VocabularyResponse)
def get_vocabulary(
    interview_id: str,
    repo: AnalysisRepository = Depends(get_analysis_repo),
) -> VocabularyResponse:
    items = repo.get_vocabulary(interview_id)
    return VocabularyResponse(
        interview_id=interview_id,
        phrases=[
            VocabularyPhrase(
                phrase=i.phrase,
                meaning=i.meaning,
                example=i.example or "",
                difficulty=i.difficulty or "",
                category=i.category or "",
                frequency=i.frequency or "",
            )
            for i in items
        ],
    )


@router.get("/{interview_id}/metrics", response_model=MetricsResponse)
def get_metrics(
    interview_id: str,
    repo: AnalysisRepository = Depends(get_analysis_repo),
) -> MetricsResponse:
    row = repo.get_metrics(interview_id)
    if not row:
        return MetricsResponse(interview_id=interview_id, metrics=None)
    return MetricsResponse(
        interview_id=interview_id,
        metrics={
            "avg_answer_length": row.avg_answer_length,
            "words_per_minute": row.words_per_minute,
            "longest_answer": row.longest_answer,
            "shortest_answer": row.shortest_answer,
            "speaking_ratio": row.speaking_ratio,
            "question_count": row.question_count,
            "answer_count": row.answer_count,
            "repeated_words": row.repeated_words,
            "filler_words": row.filler_words,
            "pauses": row.pauses,
        },
    )


@router.get("/{interview_id}/recommendations", response_model=RecommendationResponse)
def get_recommendations(
    interview_id: str,
    repo: AnalysisRepository = Depends(get_analysis_repo),
) -> RecommendationResponse:
    row = repo.get_recommendation(interview_id)
    if not row:
        return RecommendationResponse(interview_id=interview_id, recommendation=None)
    return RecommendationResponse(
        interview_id=interview_id,
        recommendation={
            "strengths": row.strengths,
            "weaknesses": row.weaknesses,
            "learning_plan": row.learning_plan,
            "english_practice": row.english_practice,
            "technical_topics": row.technical_topics,
            "summary": row.summary,
        },
    )
