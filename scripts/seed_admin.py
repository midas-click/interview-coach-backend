"""Create the initial admin user if it does not exist.

Usage::

    python -m scripts.seed_admin
"""

from __future__ import annotations

from common.config import get_settings
from database.session import build_session_factory_from_settings
from repositories.users import UserRepository
from services.auth import hash_password


def main() -> None:
    settings = get_settings()
    repo = UserRepository(build_session_factory_from_settings(settings))
    username = settings.admin_username
    if repo.get_by_username(username):
        print(f"Admin user '{username}' already exists.")
        return
    repo.create(
        username=username,
        password_hash=hash_password(settings.admin_password),
        role="admin",
    )
    print(f"Created admin user '{username}'.")


if __name__ == "__main__":
    main()
