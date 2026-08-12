"""FastAPI application factory — the composition root.

Wires the database, repos, agent registry, Inngest client, and routes
into a single ASGI application.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from inngest.fast_api import serve as inngest_serve

from agents import build_registry
from api.middleware import add_request_id_middleware
from api.routers.auth import router as auth_router
from api.routers.interviews import router as interviews_router
from api.routers.users import router as users_router
from common.config import Settings
from common.logging import setup_logging
from database.session import build_session_factory_from_settings, init_db
from orchestration.client import build_inngest_client
from orchestration.functions.interview_uploaded import make_interview_uploaded_fn
from repositories.analyses import AnalysisRepository
from repositories.interviews import InterviewRepository
from repositories.users import UserRepository
from services.deepseek import DeepSeekClient
from services.persistence import PersistenceService
from services.prompts import PromptStore
from services.s3 import DevTranscriptSource, S3TranscriptSource, TranscriptSource


def create_app(settings: Settings | None = None, *, session_factory: Any = None) -> FastAPI:
    if settings is None:
        settings = Settings()  # type: ignore[call-arg]

    setup_logging(settings.log_level)

    # ── database ────────────────────────────────────────────────────────
    if session_factory is None:
        session_factory = build_session_factory_from_settings(settings)
    if settings.database_url.startswith("sqlite"):
        # Dev / tests: create tables directly. Production migrations run at
        # deploy time via ``scripts.run_migrations`` (or the migrate Lambda) —
        # never on Lambda cold start, where concurrent invocations would race.
        init_db(settings)
    interview_repo = InterviewRepository(session_factory)
    analysis_repo = AnalysisRepository(session_factory)
    user_repo = UserRepository(session_factory)

    # ── services ────────────────────────────────────────────────────────
    try:
        llm = DeepSeekClient(settings)
    except ValueError:
        from common.logging import get_logger as _get_logger
        _get_logger(__name__).warning("DEEPSEEK_API_KEY not set — LLM agents will be unavailable")
        llm = None  # type: ignore[assignment]
    prompts = PromptStore()
    # Use local files in dev, S3 in production.
    if settings.environment == "development":
        transcript_source: TranscriptSource = DevTranscriptSource()
    else:
        transcript_source = S3TranscriptSource(settings)
    persistence = PersistenceService(interview_repo, analysis_repo)

    # ── agents ──────────────────────────────────────────────────────────
    agent_registry = build_registry(llm, prompts)

    # ── inngest ─────────────────────────────────────────────────────────
    inngest_client = build_inngest_client(settings)
    interview_uploaded_fn = make_interview_uploaded_fn(
        inngest_client, transcript_source, persistence, agent_registry
    )

    # ── app ─────────────────────────────────────────────────────────────
    app = FastAPI(
        title="Interview Intelligence Platform",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    add_request_id_middleware(app, header_name=settings.request_id_header)

    # State for DI
    app.state.settings = settings
    app.state.interview_repo = interview_repo
    app.state.analysis_repo = analysis_repo
    app.state.user_repo = user_repo

    # Routes
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(interviews_router)

    # Inngest functions served at /api/inngest
    inngest_serve(
        app,
        inngest_client,
        [interview_uploaded_fn],
        serve_origin=settings.inngest_serve_origin or None,
    )

    @app.get("/healthz")
    def health() -> dict:
        return {"status": "ok"}

    return app
