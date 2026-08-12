"""Database migrations — run at deploy time, never at Lambda cold start."""

from __future__ import annotations

from alembic.config import Config

from alembic import command


def run_migrations(database_url: str) -> None:
    """Apply all alembic migrations to ``database_url`` (idempotent)."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
