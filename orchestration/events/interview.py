"""Event schemas consumed by Inngest workflows."""

from __future__ import annotations

from pydantic import BaseModel


class InterviewUploadedPayload(BaseModel):
    interview_id: str
    bucket: str
    object_key: str
