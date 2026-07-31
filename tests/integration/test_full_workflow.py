"""End-to-end integration test: runs the full workflow with real DeepSeek.

Usage:  cd backend && python -m tests.integration.test_full_workflow
Requires: DEEPSEEK_API_KEY set in .env, demo-001.json in data/transcripts/
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from common.config import Settings
from common.logging import setup_logging
from database.session import build_session_factory_from_settings, init_db
from models.transcript import TranscriptData
from repositories.analyses import AnalysisRepository
from repositories.interviews import InterviewRepository
from sdk.agent import AgentContext
from services.deepseek import DeepSeekClient
from services.persistence import PersistenceService
from services.prompts import PromptStore
from agents import build_registry

ANALYSIS_AGENTS = ["interview_coach", "english_coach", "vocabulary", "metrics"]
_PERSIST_MAP = {
    "interview_coach": "persist_interview_analysis",
    "english_coach": "persist_english_analysis",
    "vocabulary": "persist_vocabulary",
    "metrics": "persist_metrics",
}


def _persist(persistence: PersistenceService, interview_id: str, result) -> None:
    name = _PERSIST_MAP.get(result.agent)
    if name:
        getattr(persistence, name)(interview_id, result)


async def main() -> None:
    settings = Settings()
    setup_logging("INFO")

    db_path = Path("_integration_test.db")
    settings.database_url = f"sqlite:///{db_path.resolve()}"
    init_db(settings)

    llm = DeepSeekClient(settings)
    prompts = PromptStore()
    registry = build_registry(llm, prompts)
    sf = build_session_factory_from_settings(settings)
    interview_repo = InterviewRepository(sf)
    analysis_repo = AnalysisRepository(sf)
    persistence = PersistenceService(interview_repo, analysis_repo)

    data = json.loads(open("data/transcripts/demo-001.json").read())
    transcript = TranscriptData.model_validate(data)
    iid = transcript.meeting_id
    print(f"\n{'='*60}\nInterview: {iid} | {len(transcript.transcript)} segments\n{'='*60}")

    # 1 — ensure record
    persistence.ensure_interview(iid, transcript, "local", f"interviews/{iid}.json")
    persistence.mark_processing(iid)
    print("[1] Interview record ✓")

    # 2 — parse
    print("[2] Conversation Parser...")
    result = await registry.create("conversation_parser").run(
        AgentContext(interview_id=iid, transcript=transcript)
    )
    print(f"    {result.status.value} | {result.execution_time:.1f}s")
    if result.status.value == "success":
        p = result.structured_output
        print(f"    Q: {len(p['questions'])}  A: {len(p['answers'])}  Timeline: {len(p['timeline'])}")
        persistence.persist_parser_result(iid, result)

    # 3 — parallel analysis
    print("[3] Analysis agents (parallel)...")
    ctx = AgentContext(iid, transcript, previous_outputs={"conversation_parser": result.structured_output})
    analysis_results = []
    gathered = await asyncio.gather(
        *[registry.create(n).run(ctx) for n in ANALYSIS_AGENTS if registry.has(n)],
        return_exceptions=True,
    )
    for r in gathered:
        if hasattr(r, "agent"):
            print(f"    {r.agent}: {r.status.value} | {r.execution_time:.1f}s")
            if r.status.value == "success":
                _persist(persistence, iid, r)
                analysis_results.append(r)
        else:
            print(f"    ERROR: {r}")

    # 4 — recommendation
    print("[4] Recommendation...")
    prev = {r.agent: r.structured_output for r in analysis_results}
    if registry.has("recommendation"):
        rec = await registry.create("recommendation").run(
            AgentContext(iid, transcript, previous_outputs=prev)
        )
        print(f"    {rec.status.value} | {rec.execution_time:.1f}s")
        if rec.status.value == "success":
            persistence.persist_recommendation(iid, rec)
            r = rec.structured_output
            print(f"    Strengths: {len(r['strengths'])} | Weaknesses: {len(r['weaknesses'])} | Plan: {len(r['learning_plan'])}w")

    persistence.mark_completed(iid)
    print("[5] Completed ✓")

    # Verify
    print(f"\n{'='*60}\nDB Status: {interview_repo.get(iid).status}")
    a = analysis_repo.get_interview_analysis(iid)
    if a: print(f"Score: {a.overall_score}")
    print(f"Vocabulary: {len(analysis_repo.get_vocabulary(iid))} items")
    m = analysis_repo.get_metrics(iid)
    if m: print(f"WPM: {m.words_per_minute} | Ratio: {m.speaking_ratio}")
    print(f"{'='*60}")

    db_path.unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(main())
