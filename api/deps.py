"""FastAPI dependency injection — thin accessors into app state."""

from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from common.config import Settings
from database.models import User
from repositories.analyses import AnalysisRepository
from repositories.interviews import InterviewRepository
from repositories.users import UserRepository
from services.auth import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_interview_repo(request: Request) -> InterviewRepository:
    return request.app.state.interview_repo


def get_analysis_repo(request: Request) -> AnalysisRepository:
    return request.app.state.analysis_repo


def get_user_repo(request: Request) -> UserRepository:
    return request.app.state.user_repo


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    settings = request.app.state.settings
    try:
        payload = decode_token(settings, credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = request.app.state.user_repo.get_by_username(username)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user
