"""Authentication endpoints: login and current-user lookup."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_current_user, get_settings, get_user_repo
from common.config import Settings
from database.models import User
from models.api import LoginRequest, LoginResponse, UserOut
from repositories.users import UserRepository
from services.auth import create_access_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    repo: UserRepository = Depends(get_user_repo),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    user = repo.get_by_username(body.username)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(settings, username=user.username, role=user.role)
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut(id=str(user.id), username=user.username, role=user.role),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(id=str(user.id), username=user.username, role=user.role)
