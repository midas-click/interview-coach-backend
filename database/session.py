"""Database engine and session factory."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from common.config import Settings


def build_engine(settings: Settings, **kwargs: object) -> Engine:
    engine_kwargs: dict = {"pool_pre_ping": True}
    if settings.database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine_kwargs.update(kwargs)  # type: ignore[arg-type]
    return create_engine(settings.database_url, **engine_kwargs)


def build_session_factory(engine: Engine) -> Callable[[], Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


def build_session_factory_from_settings(settings: Settings) -> Callable[[], Session]:
    return build_session_factory(build_engine(settings))
