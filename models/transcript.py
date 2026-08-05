"""Transcript payload from the desktop app (transcript.json in S3)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TranscriptSegment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    speaker: str = "Unknown"
    start: float = 0.0
    end: float = 0.0
    confidence: float = 0.0
    text: str

    @model_validator(mode="after")
    def fix_backward_timestamps(self) -> "TranscriptSegment":
        if self.end < self.start:
            self.start, self.end = self.end, self.start
        return self


class TranscriptData(BaseModel):
    """Validated transcript payload. Matches the desktop app's export format."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    meeting_id: str = Field(validation_alias="meetingId")
    company_name: str | None = Field(default=None, validation_alias="companyName")
    interview_stage: str | None = Field(default=None, validation_alias="interviewStage")
    created_at: datetime | None = Field(default=None, validation_alias="createdAt")
    language: str = "en"
    transcript: list[TranscriptSegment] = Field(min_length=1)
