import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    default_branch: str = "main"

    model_config = {"str_strip_whitespace": True}

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("Project name must not be empty")
        if len(v) > 255:
            raise ValueError("Project name must be 255 characters or fewer")
        return v

    @field_validator("default_branch")
    @classmethod
    def branch_not_empty(cls, v: str) -> str:
        return v.strip() or "main"


class ProjectSummary(BaseModel):
    """Matches the Project interface in frontend/src/data.ts."""

    id: uuid.UUID
    name: str
    # quality_gate_passed translated to "Passed" | "Failed" for frontend compat
    status: str
    bugs: int
    vulnerabilities: int
    code_smells: int
    coverage: str | None
    last_analysis: str | None
    branch: str
    source_type: str | None
    archived: bool
    risk_score: float | None = None

    model_config = {"from_attributes": True}


class QualityGate(BaseModel):
    passed: bool
    failed_conditions: list[str]


class KeyMetrics(BaseModel):
    bugs: int
    bugs_delta: int | None
    vulnerabilities: int
    critical_vulnerabilities: int
    high_vulnerabilities: int
    code_smells: int
    technical_debt_display: str | None
    security_hotspots: int
    security_hotspots_needing_review: int


class SupportingMetrics(BaseModel):
    coverage_pct: float | None
    coverage_target_pct: float | None
    duplications_pct: float | None
    technical_debt_display: str | None
    maintainability_rating: str | None


class PriorityIssue(BaseModel):
    id: uuid.UUID
    severity: str
    type: str
    title: str
    rule: str | None
    file: str | None
    line: int | None
    risk: str
    status: str


class DashboardResponse(BaseModel):
    project_id: uuid.UUID
    project_name: str
    branch: str
    last_analysis_at: datetime | None
    analysis_job_id: uuid.UUID | None
    quality_gate: QualityGate
    metrics: KeyMetrics
    supporting_metrics: SupportingMetrics
    priority_issues: list[PriorityIssue]
    # Risk score fields (FR-RISK-01, FR-RISK-03, FR-RISK-07)
    risk_score: float | None = None
    risk_score_version: str | None = None
    open_findings: int = 0
    findings_by_severity: dict[str, int] = {}
