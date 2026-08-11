"""Admin-only user management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_user_repo, require_admin
from models.api import UserCreate, UserOut, UserUpdate
from repositories.users import UserRepository
from services.auth import hash_password

router = APIRouter(
    prefix="/api/users",
    tags=["users"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=list[UserOut])
def list_users(repo: UserRepository = Depends(get_user_repo)) -> list[UserOut]:
    return [UserOut(id=str(u.id), username=u.username, role=u.role) for u in repo.list()]


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    body: UserCreate,
    repo: UserRepository = Depends(get_user_repo),
) -> UserOut:
    if repo.get_by_username(body.username):
        raise HTTPException(status_code=409, detail="Username already exists")
    user = repo.create(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    return UserOut(id=str(user.id), username=user.username, role=user.role)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    body: UserUpdate,
    repo: UserRepository = Depends(get_user_repo),
) -> UserOut:
    user = repo.update(
        user_id,
        username=body.username,
        role=body.role,
        password_hash=hash_password(body.password) if body.password else None,
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(id=str(user.id), username=user.username, role=user.role)


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: str,
    repo: UserRepository = Depends(get_user_repo),
) -> None:
    if not repo.delete(user_id):
        raise HTTPException(status_code=404, detail="User not found")
