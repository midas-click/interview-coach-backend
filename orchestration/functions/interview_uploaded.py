"""Inngest function: interview/uploaded → full processing pipeline."""

from __future__ import annotations

from typing import Any

import inngest

from common.logging import get_logger
from orchestration.workflows.interview_uploaded import InterviewUploadedWorkflow
from sdk.agent import AgentRegistry
from services.persistence import PersistenceService
from services.s3 import TranscriptSource

logger = get_logger("inngest.functions.interview_uploaded")


def make_interview_uploaded_fn(
    client: inngest.Inngest,
    transcript_source: TranscriptSource,
    persistence: PersistenceService,
    agent_registry: AgentRegistry,
) -> inngest.Function[Any]:
    """Create the Inngest function for processing uploaded interview transcripts."""

    workflow = InterviewUploadedWorkflow(transcript_source, persistence, agent_registry)

    @client.create_function(
        fn_id="interview-uploaded-workflow",
        trigger=inngest.TriggerEvent(event="interview/uploaded"),
        retries=5,
    )
    async def handle(
        ctx: inngest.Context,
    ) -> dict[str, Any]:
        step = ctx.step
        payload: dict[str, Any] = ctx.event.data
        logger.info(
            "workflow started",
            extra={
                "run_id": ctx.run_id,
                "interview_id": payload.get("interview_id"),
            },
        )
        await workflow.run(payload, step)
        return {"interview_id": payload.get("interview_id"), "status": "processed"}

    return handle
