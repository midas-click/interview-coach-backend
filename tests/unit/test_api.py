"""REST API endpoint tests (in-memory, no server)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from common.config import Settings
from services.auth import hash_password


@pytest.fixture
def client(tmp_path: Any) -> TestClient:
    db_path = tmp_path / "test.db"
    database_url = f"sqlite:///{db_path}"
    settings = Settings(
        _env_file=None,
        database_url=database_url,
        deepseek_api_key="fake-for-test",
        jwt_secret_key="test-secret",
    )
    app = create_app(settings)
    app.state.user_repo.create(
        username="admin", password_hash=hash_password("admin123"), role="admin"
    )
    app.state.user_repo.create(
        username="viewer", password_hash=hash_password("viewer123"), role="user"
    )
    return TestClient(app)


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    return _login(client, "admin", "admin123")


@pytest.fixture
def user_headers(client: TestClient) -> dict[str, str]:
    return _login(client, "viewer", "viewer123")


def test_healthz(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ── auth ────────────────────────────────────────────────────────────────

def test_login_success(client: TestClient) -> None:
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["username"] == "admin"
    assert body["user"]["role"] == "admin"


def test_login_invalid(client: TestClient) -> None:
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_me(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.get("/api/auth/me", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


def test_me_unauthenticated(client: TestClient) -> None:
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


# ── interviews require auth ─────────────────────────────────────────────

def test_list_interviews_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/interviews")
    assert resp.status_code == 401


def test_list_interviews_empty(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.get("/api/interviews", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_list_interviews_paginated(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.get(
        "/api/interviews?limit=1&offset=0", headers=admin_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert isinstance(body["items"], list)
    assert isinstance(body["total"], int)


def test_get_interview_not_found(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.get("/api/interviews/nonexistent", headers=admin_headers)
    assert resp.status_code == 404


def test_get_analysis_empty(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.get("/api/interviews/nonexistent/analysis", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["analysis"] is None


def test_get_english_empty(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.get("/api/interviews/nonexistent/english", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["english"] is None


def test_get_vocabulary_empty(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.get("/api/interviews/nonexistent/vocabulary", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["phrases"] == []


def test_get_metrics_empty(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.get("/api/interviews/nonexistent/metrics", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["metrics"] is None


def test_get_recommendations_empty(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.get("/api/interviews/nonexistent/recommendations", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["recommendation"] is None


def test_user_can_view_interviews(client: TestClient, user_headers: dict[str, str]) -> None:
    resp = client.get("/api/interviews", headers=user_headers)
    assert resp.status_code == 200


def test_user_cannot_delete_interview(client: TestClient, user_headers: dict[str, str]) -> None:
    resp = client.delete("/api/interviews/nonexistent", headers=user_headers)
    assert resp.status_code == 403


# ── user management (admin only) ─────────────────────────────────────────

def test_list_users_admin(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.get("/api/users", headers=admin_headers)
    assert resp.status_code == 200
    usernames = {u["username"] for u in resp.json()}
    assert usernames == {"admin", "viewer"}


def test_list_users_forbidden_for_user(client: TestClient, user_headers: dict[str, str]) -> None:
    resp = client.get("/api/users", headers=user_headers)
    assert resp.status_code == 403


def test_create_user(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.post(
        "/api/users",
        headers=admin_headers,
        json={"username": "newbie", "password": "pass123", "role": "user"},
    )
    assert resp.status_code == 201
    assert resp.json()["username"] == "newbie"
    # new user can log in
    login = client.post("/api/auth/login", json={"username": "newbie", "password": "pass123"})
    assert login.status_code == 200


def test_create_user_duplicate(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.post(
        "/api/users",
        headers=admin_headers,
        json={"username": "admin", "password": "x", "role": "user"},
    )
    assert resp.status_code == 409


def test_update_user(client: TestClient, admin_headers: dict[str, str]) -> None:
    users = client.get("/api/users", headers=admin_headers).json()
    target = next(u for u in users if u["username"] == "viewer")
    resp = client.put(
        f"/api/users/{target['id']}",
        headers=admin_headers,
        json={"username": "viewer2", "role": "user", "password": "newpass"},
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "viewer2"
    login = client.post("/api/auth/login", json={"username": "viewer2", "password": "newpass"})
    assert login.status_code == 200


def test_delete_user(client: TestClient, admin_headers: dict[str, str]) -> None:
    users = client.get("/api/users", headers=admin_headers).json()
    target = next(u for u in users if u["username"] == "viewer")
    resp = client.delete(f"/api/users/{target['id']}", headers=admin_headers)
    assert resp.status_code == 204
    login = client.post("/api/auth/login", json={"username": "viewer", "password": "viewer123"})
    assert login.status_code == 401


def test_request_id_header(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert "X-Request-ID" in resp.headers
    import uuid
    uuid.UUID(resp.headers["X-Request-ID"])
