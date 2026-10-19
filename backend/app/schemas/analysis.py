import uuid
from datetime import datetime

from pydantic import BaseModel


class AnalysisJobStatus(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    status: str   # queued | running | completed | failed | cancelled
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    failure_reason: str | None = None
    engine_name: str | None = None
    engine_version: str | None = None
    # Populated when status == completed
    findings_count: int | None = None
    bugs_count: int = 0
    vulnerabilities_count: int = 0
    code_smells_count: int = 0
    security_hotspots_count: int = 0

    model_config = {"from_attributes": True}
