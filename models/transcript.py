"""Transcript payload from the desktop app (transcript.json in S3)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class TranscriberMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")
    model: str = "whisper-base"
    language: str = "en"
    created_at: datetime | None = Field(default=None, validation_alias="createdAt")


class TranscriptSegment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int | None = None
    speaker: str = "unknown"
    start_ms: int = Field(default=0, validation_alias="startMs")
    end_ms: int = Field(default=0, validation_alias="endMs")
    confidence: float = 0.0
    text: str

    @model_validator(mode="before")
    @classmethod
    def _convert_legacy_fields(cls, data: Any) -> Any:
        """Accept legacy float start/end fields and convert to startMs/endMs."""
        if isinstance(data, dict):
            if "start" in data and "startMs" not in data:
                data["startMs"] = int(data.pop("start") * 1000)
            if "end" in data and "endMs" not in data:
                data["endMs"] = int(data.pop("end") * 1000)
        return data

    @computed_field
    @property
    def start(self) -> float:
        return self.start_ms / 1000.0

    @computed_field
    @property
    def end(self) -> float:
        return self.end_ms / 1000.0

    @model_validator(mode="after")
    def fix_backward_timestamps(self) -> TranscriptSegment:
        if self.end_ms < self.start_ms:
            self.start_ms, self.end_ms = self.end_ms, self.start_ms
        return self


class TranscriptData(BaseModel):
    """Validated transcript payload. Supports both legacy (desktop app v1) and v2 format."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    interview_id: str = Field(validation_alias="interviewId")
    company_name: str | None = Field(default=None, validation_alias="company")
    interview_stage: str | None = Field(default=None, validation_alias="stage")
    schema_version: int = Field(default=1, validation_alias="schemaVersion")
    transcriber: TranscriberMeta = Field(default_factory=TranscriberMeta)
    created_at: datetime | None = Field(default=None, validation_alias="createdAt")
    language: str = "en"
    utterances: list[TranscriptSegment] = Field(default_factory=list, min_length=1)

    @property
    def transcript(self) -> list[TranscriptSegment]:
        """Convenience alias — agents use .transcript to access segments."""
        return self.utterances
