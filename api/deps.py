"""FastAPI dependency injection — thin accessors into app state."""

from __future__ import annotations

from fastapi import Request

from common.config import Settings
from repositories.analyses import AnalysisRepository
from repositories.interviews import InterviewRepository


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_interview_repo(request: Request) -> InterviewRepository:
    return request.app.state.interview_repo


def get_analysis_repo(request: Request) -> AnalysisRepository:
    return request.app.state.analysis_repo
