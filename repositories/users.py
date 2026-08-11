"""User persistence."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import User

SessionFactory = Callable[[], Session]


class UserRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def get(self, user_id: str) -> User | None:
        with self._session_factory() as session:
            return session.get(User, uuid.UUID(user_id))

    def get_by_username(self, username: str) -> User | None:
        with self._session_factory() as session:
            return session.execute(
                select(User).where(User.username == username)
            ).scalar_one_or_none()

    def list(self) -> list[User]:
        with self._session_factory() as session:
            return list(session.execute(select(User).order_by(User.username)).scalars())

    def create(self, *, username: str, password_hash: str, role: str) -> User:
        with self._session_factory() as session:
            user = User(username=username, password_hash=password_hash, role=role)
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    def update(
        self,
        user_id: str,
        *,
        username: str,
        role: str,
        password_hash: str | None,
    ) -> User | None:
        with self._session_factory() as session:
            existing = session.get(User, uuid.UUID(user_id))
            if existing is None:
                return None
            existing.username = username
            existing.role = role
            if password_hash:
                existing.password_hash = password_hash
            session.commit()
            session.refresh(existing)
            return existing

    def delete(self, user_id: str) -> bool:
        with self._session_factory() as session:
            user = session.get(User, uuid.UUID(user_id))
            if user is None:
                return False
            session.delete(user)
            session.commit()
            return True
