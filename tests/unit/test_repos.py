"""Repository tests (sqlite in-memory)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from database.models import Base
from repositories.analyses import AnalysisRepository
from repositories.interviews import InterviewRepository


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


@pytest.fixture
def interview_repo(session_factory) -> InterviewRepository:
    return InterviewRepository(session_factory)


@pytest.fixture
def analysis_repo(session_factory) -> AnalysisRepository:
    return AnalysisRepository(session_factory)


# ── InterviewRepository ────────────────────────────────────────────────────

def test_create_and_get_interview(interview_repo) -> None:
    interview_repo.create_if_missing("itv-1", company_name="ACME", interview_stage="final", language="en")
    row = interview_repo.get("itv-1")
    assert row is not None
    assert row.interview_id == "itv-1"
    assert row.company_name == "ACME"
    assert row.status == "uploaded"


def test_create_if_missing_is_idempotent(interview_repo) -> None:
    first = interview_repo.create_if_missing("itv-2", company_name="A", interview_stage=None, language="en")
    second = interview_repo.create_if_missing("itv-2", company_name="B", interview_stage=None, language="en")
    assert first.id == second.id
    assert interview_repo.get("itv-2").company_name == "A"  # unchanged


def test_update_status(interview_repo) -> None:
    interview_repo.create_if_missing("itv-3", company_name=None, interview_stage=None, language="en")
    interview_repo.update_status("itv-3", "completed")
    assert interview_repo.get("itv-3").status == "completed"


def test_list_paginates(interview_repo) -> None:
    for i in range(5):
        interview_repo.create_if_missing(f"itv-{i}", company_name=None, interview_stage=None, language="en")
    results = interview_repo.list(limit=3, offset=1)
    assert len(results) == 3


# ── Transcript ─────────────────────────────────────────────────────────────

def test_persist_parser_result_keeps_raw_transcript(interview_repo, analysis_repo) -> None:
    """Regression: persisting parsed Q/A must not clobber the raw transcript row."""
    from sdk.agent import AgentResult
    from services.persistence import PersistenceService

    interview_repo.create_if_missing("itv-10", company_name="ACME", interview_stage="tech", language="en")
    interview_repo.save_transcript(
        "itv-10", bucket="b", object_key="k", raw_json={"utterances": [{"text": "hello"}]}
    )

    svc = PersistenceService(interview_repo, analysis_repo)
    svc.persist_parser_result(
        "itv-10",
        AgentResult(
            agent="conversation_parser",
            structured_output={
                "questions": [{"id": "q1", "sequence": 1, "text": "Q?", "speaker": "Interviewer"}],
                "answers": [],
            },
        ),
    )

    t = interview_repo.get_transcript("itv-10")
    assert t is not None
    assert t.raw_json == {"utterances": [{"text": "hello"}]}  # not overwritten with {}
    assert len(interview_repo.get_questions("itv-10")) == 1


def test_save_transcript_writes_once(interview_repo) -> None:
    interview_repo.create_if_missing("itv-4", company_name=None, interview_stage=None, language="en")
    interview_repo.save_transcript("itv-4", bucket="b", object_key="k", raw_json={"a": 1})
    t = interview_repo.get_transcript("itv-4")
    assert t is not None
    assert t.raw_json == {"a": 1}

    # Second write NOW overwrites raw_json (fresh run = fresh data).
    interview_repo.save_transcript("itv-4", bucket="b", object_key="k", raw_json={"a": 2}, parsed_timeline=[{"x": "y"}])
    t2 = interview_repo.get_transcript("itv-4")
    assert t2.raw_json == {"a": 2}   # overwritten with new data
    assert t2.parsed_timeline == [{"x": "y"}]


# ── Q/A ────────────────────────────────────────────────────────────────────

def test_replace_questions_and_answers(interview_repo) -> None:
    interview_repo.create_if_missing("itv-5", company_name=None, interview_stage=None, language="en")
    interview_repo.replace_questions("itv-5", [
        {"id": "q1", "sequence": 1, "text": "Question A", "speaker": "Interviewer", "start": 0.0, "end": 2.0},
    ])
    qs = interview_repo.get_questions("itv-5")
    assert len(qs) == 1
    q_id = qs[0].id

    interview_repo.replace_answers("itv-5", [
        {"question_id": None, "sequence": 1, "text": "Answer A", "speaker": "Candidate", "start": 2.0, "end": 5.0},
    ], {None: q_id})
    answers = interview_repo.get_answers("itv-5")
    assert len(answers) == 1

    # Replace is idempotent.
    interview_repo.replace_questions("itv-5", [])
    assert len(interview_repo.get_questions("itv-5")) == 0


# ── AnalysisRepository ─────────────────────────────────────────────────────

@pytest.fixture
def _ensure_interview(interview_repo: InterviewRepository) -> None:
    interview_repo.create_if_missing("itv-99", company_name=None, interview_stage=None, language="en")


def test_upsert_analysis(analysis_repo: AnalysisRepository, _ensure_interview: None) -> None:
    row = analysis_repo.upsert_interview_analysis(
        "itv-99",
        overall_score=8.0,
        dimensions={"tq": {"score": 7}},
        summary="Good",
        model="m",
        prompt_version="1.0",
        raw={},
    )
    assert row.overall_score == 8.0
    assert row.dimensions == {"tq": {"score": 7}}

    # Upsert updates.
    analysis_repo.upsert_interview_analysis(
        "itv-99", overall_score=9.0, dimensions={}, summary="Better", model="m", prompt_version="1.0", raw={}
    )
    assert analysis_repo.get_interview_analysis("itv-99").overall_score == 9.0


def test_replace_vocabulary(analysis_repo: AnalysisRepository, _ensure_interview: None) -> None:
    analysis_repo.replace_vocabulary("itv-99", [
        {"phrase": "walk me through", "meaning": "explain", "example": "...",
         "difficulty": "intermediate", "category": "question", "frequency": "common"},
    ])
    items = analysis_repo.get_vocabulary("itv-99")
    assert len(items) == 1
    assert items[0].phrase == "walk me through"


def test_upsert_recommendation_with_topics(analysis_repo: AnalysisRepository, _ensure_interview: None) -> None:
    rec = analysis_repo.upsert_recommendation(
        "itv-99",
        strengths=[{"title": "S"}],
        weaknesses=[{"title": "W"}],
        learning_plan=[{"week": 1, "focus": "X", "actions": []}],
        english_practice=[],
        technical_topics=[{"topic": "DB scaling", "priority": "high"}],
        summary="...",
        model="m",
        prompt_version="1.0",
        raw={},
    )
    analysis_repo.replace_learning_topics(rec.id, [{"topic": "DB scaling", "priority": "high"}])
    assert rec.strengths == [{"title": "S"}]
