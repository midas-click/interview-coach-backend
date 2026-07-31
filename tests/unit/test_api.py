"""REST API endpoint tests (in-memory, no server)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from common.config import Settings


@pytest.fixture
def client(tmp_path: Any) -> TestClient:
    import os
    db_path = tmp_path / "test.db"
    database_url = f"sqlite:///{db_path}"
    settings = Settings(
        _env_file=None,
        database_url=database_url,
        deepseek_api_key="fake-for-test",
    )
    app = create_app(settings)
    return TestClient(app)


def test_healthz(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_interviews_empty(client: TestClient) -> None:
    resp = client.get("/interviews")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_interview_not_found(client: TestClient) -> None:
    resp = client.get("/interviews/nonexistent")
    assert resp.status_code == 404


def test_get_analysis_empty(client: TestClient) -> None:
    resp = client.get("/interviews/nonexistent/analysis")
    assert resp.status_code == 200
    assert resp.json()["analysis"] is None


def test_get_english_empty(client: TestClient) -> None:
    resp = client.get("/interviews/nonexistent/english")
    assert resp.status_code == 200
    assert resp.json()["english"] is None


def test_get_vocabulary_empty(client: TestClient) -> None:
    resp = client.get("/interviews/nonexistent/vocabulary")
    assert resp.status_code == 200
    assert resp.json()["phrases"] == []


def test_get_metrics_empty(client: TestClient) -> None:
    resp = client.get("/interviews/nonexistent/metrics")
    assert resp.status_code == 200
    assert resp.json()["metrics"] is None


def test_get_recommendations_empty(client: TestClient) -> None:
    resp = client.get("/interviews/nonexistent/recommendations")
    assert resp.status_code == 200
    assert resp.json()["recommendation"] is None


def test_request_id_header(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert "X-Request-ID" in resp.headers
    import uuid
    # should be a valid UUID
    uuid.UUID(resp.headers["X-Request-ID"])
