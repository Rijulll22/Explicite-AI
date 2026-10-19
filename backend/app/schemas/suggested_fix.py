"""Pydantic schemas for suggested-fix endpoints."""
import uuid
from datetime import datetime

from pydantic import BaseModel


class FixGenerateRequest(BaseModel):
    """No body fields required; the finding and project are path parameters."""
    pass


class FixResponse(BaseModel):
    """Full fix record returned by generate, detail, approve, and reject endpoints."""
    id: uuid.UUID
    finding_id: uuid.UUID
    project_id: uuid.UUID
    analysis_job_id: uuid.UUID

    target_file: str | None
    original_snippet: str | None
    proposed_snippet: str | None
    unified_diff: str | None
    snippet_start_line: int | None
    snippet_end_line: int | None

    rationale: str | None
    caveats: str | None

    status: str
    source_available: bool

    model_provider: str | None
    model_name: str | None

    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None
    rejected_at: datetime | None
    applied_at: datetime | None

    class Config:
        from_attributes = True


class FixSummary(BaseModel):
    """Lightweight record returned in lists."""
    id: uuid.UUID
    finding_id: uuid.UUID
    status: str
    target_file: str | None
    model_provider: str | None
    model_name: str | None
    created_at: datetime

    class Config:
        from_attributes = True
