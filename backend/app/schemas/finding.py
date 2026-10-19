import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator, model_validator

_VALID_STATUSES = {"Open", "In Review", "Resolved"}


class FindingSummary(BaseModel):
    """
    Matches the Issue interface in frontend/src/data.ts.
    Field names mirror the TypeScript interface exactly so that wiring up
    fetch calls in the frontend requires no renaming.
    """

    id: uuid.UUID
    # Original engine severity (SRS FR-AN-03: preserved separately)
    severity: str   # Critical | High | Medium | Low
    type: str       # Vulnerability | Bug | Code Smell | Security Hotspot
    title: str
    rule: str | None
    file: str | None
    line: int | None
    # Explicite AI risk score (SRS FR-RISK-01)
    risk: str       # High | Medium | Low
    status: str     # Open | In Review | Resolved
    created_at: datetime

    model_config = {"from_attributes": True}


class FindingDetail(BaseModel):
    id: uuid.UUID
    severity: str
    type: str
    title: str
    rule: str | None
    file: str | None
    line: int | None
    risk: str
    risk_score: float | None
    risk_score_version: str | None
    status: str
    description: str | None
    ai_explanation: str | None
    cwe_id: str | None
    owasp_category: str | None
    cvss_score: float | None
    cvss_vector: str | None
    cvss_version: str | None
    cvss_severity: str | None    # derived from cvss_score on construction
    analysis_job_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _derive_cvss_severity(cls, data):
        if isinstance(data, dict):
            score = data.get("cvss_score")
            if score is not None and data.get("cvss_severity") is None:
                from app.services.cvss_scoring import _v31_severity
                data = dict(data)
                data["cvss_severity"] = _v31_severity(float(score))
        return data


# ── Source excerpt ─────────────────────────────────────────────────────────────

class SourceLineSchema(BaseModel):
    number: int
    content: str
    is_target: bool


class SourceExcerptResponse(BaseModel):
    available: bool
    file: str
    target_line: int | None
    lines: list[SourceLineSchema]
    message: str | None


class FindingListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[FindingSummary]


class FindingStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        if v not in _VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(_VALID_STATUSES)}")
        return v
