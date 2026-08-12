"""CLI: apply alembic migrations to the configured database.

Usage::

    DATABASE_URL=postgresql+psycopg://... python -m scripts.run_migrations
"""

from __future__ import annotations

from common.config import get_settings
from common.logging import setup_logging
from database.migrate import run_migrations


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    run_migrations(settings.database_url)
    host = settings.database_url.split("@")[-1].split("/")[0]
    print(f"migrations applied (database host: {host})")


if __name__ == "__main__":
    main()
