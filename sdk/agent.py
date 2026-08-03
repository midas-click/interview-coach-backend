"""Core Agent SDK: uniform agent interface + factory registry.

Every agent exposes ``run(context) -> AgentResult``. The base class owns
cross-cutting concerns (timing, failure capture, prompt versioning) so
individual agents only implement ``_execute``.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, Field

from common.logging import get_logger, set_interview_id
from models.transcript import TranscriptData
from sdk.llm import LLMClient
from services.prompts import PromptStore

logger = get_logger("sdk.agent")


class AgentStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentContext(BaseModel):
    """Everything an agent needs to perform its task."""

    interview_id: str
    transcript: TranscriptData
    metadata: dict[str, Any] = Field(default_factory=dict)
    previous_outputs: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """Uniform result envelope produced by every agent."""

    agent: str
    status: AgentStatus = AgentStatus.SUCCESS
    execution_time: float = 0.0
    model: str | None = None
    prompt_version: str | None = None
    structured_output: Any = None
    error: str | None = None
    estimated_cost_usd: float = 0.0


class BaseAgent(ABC):
    """Interface all agents implement. Set ``name`` and implement ``_execute``."""

    name: str = ""
    prompt_name: str | None = None

    def __init__(self, llm: LLMClient | None = None, prompt_store: PromptStore | None = None) -> None:
        self._llm = llm
        self._prompts = prompt_store

    async def run(self, context: AgentContext) -> AgentResult:
        """Execute and always return a typed ``AgentResult``."""
        started = time.perf_counter()
        set_interview_id(context.interview_id)
        try:
            output = await self._execute(context)
            return AgentResult(
                agent=self.name,
                status=AgentStatus.SUCCESS,
                execution_time=time.perf_counter() - started,
                model=self._llm.model if self._llm else None,
                prompt_version=self._current_prompt_version(),
                structured_output=output,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "agent failed",
                extra={"agent": self.name, "interview_id": context.interview_id},
            )
            return AgentResult(
                agent=self.name,
                status=AgentStatus.FAILED,
                execution_time=time.perf_counter() - started,
                model=self._llm.model if self._llm else None,
                prompt_version=self._current_prompt_version(),
                error=str(exc),
            )

    @abstractmethod
    async def _execute(self, context: AgentContext) -> Any:
        """Perform the task and return structured output."""

    def _current_prompt_version(self) -> str | None:
        if self.prompt_name and self._prompts is not None:
            try:
                return self._prompts.get(self.prompt_name).version
            except KeyError:
                return None
        return None

    @staticmethod
    def _transcript_json(transcript: Any) -> str:
        """Serialise transcript segments to a JSON string (shared by agents)."""
        import json as _json
        return _json.dumps([s.model_dump() for s in transcript.transcript], indent=2)

    @staticmethod
    def _chunk_segments(segments: list, size: int, overlap: int = 0) -> list[list]:
        """Split segments into overlapping batches for chunked LLM calls."""
        batches = []
        i = 0
        while i < len(segments):
            batch = segments[i:i + size]
            batches.append(batch)
            i += size - overlap
        return batches

    @staticmethod
    def _filter_transcript(transcript: Any, speaker: str) -> Any:
        """Return a copy of the transcript containing only one speaker's segments."""
        from models.transcript import TranscriptData as _TD
        filtered = [s for s in transcript.transcript if s.speaker.lower() == speaker.lower()]
        if not filtered:
            return transcript  # fallback to full transcript
        return _TD(
            meeting_id=transcript.meeting_id,
            company_name=transcript.company_name,
            interview_stage=transcript.interview_stage,
            language=transcript.language,
            created_at=transcript.created_at,
            transcript=filtered,
        )


class AgentRegistry:
    """Factory registry: agent name → callable returning a configured agent."""

    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], BaseAgent]] = {}

    def register(self, name: str, factory: Callable[[], BaseAgent]) -> None:
        if name in self._factories:
            raise ValueError(f"agent already registered: {name}")
        self._factories[name] = factory

    def create(self, name: str) -> BaseAgent:
        try:
            return self._factories[name]()
        except KeyError as exc:
            raise KeyError(f"unknown agent: {name}") from exc

    def names(self) -> list[str]:
        return sorted(self._factories)

    def has(self, name: str) -> bool:
        return name in self._factories
