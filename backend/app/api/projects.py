import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbDep, get_project_membership
from app.models.analysis import AnalysisJob
from app.models.finding import Finding
from app.models.project import Project, ProjectMembership
from app.schemas.project import (
    DashboardResponse,
    KeyMetrics,
    PriorityIssue,
    ProjectCreate,
    ProjectSummary,
    QualityGate,
    SupportingMetrics,
)
from app.schemas.auth import UserPreferences
from app.services import quality_gate as qg_service
from app.services import risk_scoring

router = APIRouter(prefix="/projects", tags=["projects"])


def _format_technical_debt(minutes: int | None) -> str | None:
    if minutes is None:
        return None
    days, rem = divmod(minutes, 60 * 8)  # 8-hour working day
    hours, mins = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins and not days:
        parts.append(f"{mins}m")
    return " ".join(parts) if parts else "0m"


def _coverage_display(pct: float | None) -> str | None:
    return f"{pct:.1f}%" if pct is not None else None


def _relative_time(dt: datetime | None) -> str | None:
    """Very simple relative-time string for display; production would use a proper library."""
    if dt is None:
        return None
    now = datetime.now(tz=timezone.utc)
    diff = now - dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60} minutes ago"
    if seconds < 86400:
        h = seconds // 3600
        return f"{h} hour{'s' if h > 1 else ''} ago"
    d = seconds // 86400
    return f"{d} day{'s' if d > 1 else ''} ago"


@router.post("", response_model=ProjectSummary, status_code=201)
async def create_project(
    body: ProjectCreate, current_user: CurrentUser, db: DbDep
) -> ProjectSummary:
    """
    Create a new project owned by the authenticated user.
    The owner is automatically added as a member with the 'owner' role.
    """
    project = Project(
        id=uuid.uuid4(),
        name=body.name,
        description=body.description,
        default_branch=body.default_branch,
        owner_id=current_user.id,
    )
    db.add(project)
    await db.flush()
    membership = ProjectMembership(
        project_id=project.id,
        user_id=current_user.id,
        role="owner",
    )
    db.add(membership)
    await db.flush()
    return _project_to_summary(project, None)


@router.get("", response_model=list[ProjectSummary])
async def list_projects(current_user: CurrentUser, db: DbDep) -> list[ProjectSummary]:
    """
    Return all non-archived projects the current user is a member of.
    Metrics are sourced from the latest completed analysis job.
    System admins see all projects.
    """
    if current_user.system_role == "system_admin":
        result = await db.execute(
            select(Project).where(Project.archived_at.is_(None))
        )
        projects = result.scalars().all()
    else:
        result = await db.execute(
            select(Project)
            .join(
                ProjectMembership,
                (ProjectMembership.project_id == Project.id)
                & (ProjectMembership.user_id == current_user.id),
            )
            .where(Project.archived_at.is_(None))
        )
        projects = result.scalars().all()

    summaries: list[ProjectSummary] = []
    for project in projects:
        job = await _latest_completed_job(db, project.id)
        summaries.append(_project_to_summary(project, job))
    return summaries


@router.get("/{project_id}/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    project_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> DashboardResponse:
    """
    Return dashboard metrics for a project.
    Requires project membership.
    Metrics come from the latest completed analysis job.
    """
    project, _ = await get_project_membership(project_id, current_user, db)
    job = await _latest_completed_job(db, project_id)

    if job is None:
        gate = qg_service.evaluate(0, 0, no_analysis=True)
        return DashboardResponse(
            project_id=project.id,
            project_name=project.name,
            branch=project.default_branch,
            last_analysis_at=None,
            analysis_job_id=None,
            quality_gate=QualityGate(
                passed=gate.passed, failed_conditions=gate.failed_conditions
            ),
            metrics=KeyMetrics(
                bugs=0,
                bugs_delta=None,
                vulnerabilities=0,
                critical_vulnerabilities=0,
                high_vulnerabilities=0,
                code_smells=0,
                technical_debt_display=None,
                security_hotspots=0,
                security_hotspots_needing_review=0,
            ),
            supporting_metrics=SupportingMetrics(
                coverage_pct=None,
                coverage_target_pct=80.0,
                duplications_pct=None,
                technical_debt_display=None,
                maintainability_rating=None,
            ),
            priority_issues=[],
            risk_score=None,
            risk_score_version=None,
            open_findings=0,
            findings_by_severity={},
        )

    # Load all findings for this job in one query — used for risk score,
    # counts, priority issues, and severity breakdown.
    all_findings_result = await db.execute(
        select(Finding).where(Finding.analysis_job_id == job.id)
    )
    all_findings: list[Finding] = list(all_findings_result.scalars().all())

    # ── Risk score (FR-RISK-01, FR-RISK-03) ──────────────────────────────────
    r_score = risk_scoring.project_risk_score(all_findings)
    r_version = risk_scoring.SCORING_VERSION if all_findings else None

    # ── Open/unresolved count and severity breakdown ──────────────────────────
    open_count = sum(1 for f in all_findings if f.status != "Resolved")
    by_sev: dict[str, int] = {}
    for f in all_findings:
        by_sev[f.engine_severity] = by_sev.get(f.engine_severity, 0) + 1

    # ── Priority issues: Critical + High, open, up to 5 ──────────────────────
    _sev_order = {"Critical": 0, "High": 1}
    priority_candidates = [
        f for f in all_findings
        if f.engine_severity in ("Critical", "High") and f.status == "Open"
    ]
    priority_candidates.sort(key=lambda f: (_sev_order.get(f.engine_severity, 99), f.title))
    priority_issues = [
        PriorityIssue(
            id=f.id,
            severity=f.engine_severity,
            type=f.issue_type,
            title=f.title,
            rule=f.rule_key,
            file=f.file_path,
            line=f.line_number,
            risk=f.risk_level,
            status=f.status,
        )
        for f in priority_candidates[:5]
    ]

    # ── Security hotspots needing review ─────────────────────────────────────
    open_hotspots = sum(
        1 for f in all_findings
        if f.issue_type == "Security Hotspot" and f.status == "Open"
    )

    # ── Vulnerability severity breakdown ─────────────────────────────────────
    vulns_only = [f for f in all_findings if f.issue_type == "Vulnerability"]
    critical_vulns = sum(1 for v in vulns_only if v.engine_severity == "Critical")
    high_vulns = sum(1 for v in vulns_only if v.engine_severity == "High")

    # ── Quality gate (conditions reflect the current user's thresholds) ──────
    prefs = UserPreferences.model_validate(current_user.preferences or {})
    gate = qg_service.evaluate(
        job.bugs_count,
        job.vulnerabilities_count,
        job.coverage_pct,
        max_bugs=prefs.quality_gate_max_bugs,
        max_vulnerabilities=prefs.quality_gate_max_vulnerabilities,
        enforce_coverage=prefs.quality_gate_coverage_threshold > 0,
        coverage_target_pct=prefs.quality_gate_coverage_threshold,
    )

    return DashboardResponse(
        project_id=project.id,
        project_name=project.name,
        branch=job.source_branch or project.default_branch,
        last_analysis_at=job.completed_at,
        analysis_job_id=job.id,
        quality_gate=QualityGate(
            passed=bool(job.quality_gate_passed),
            failed_conditions=gate.failed_conditions,
        ),
        metrics=KeyMetrics(
            bugs=job.bugs_count,
            bugs_delta=None,
            vulnerabilities=job.vulnerabilities_count,
            critical_vulnerabilities=critical_vulns,
            high_vulnerabilities=high_vulns,
            code_smells=job.code_smells_count,
            technical_debt_display=_format_technical_debt(job.technical_debt_minutes),
            security_hotspots=job.security_hotspots_count,
            security_hotspots_needing_review=open_hotspots,
        ),
        supporting_metrics=SupportingMetrics(
            coverage_pct=job.coverage_pct,
            coverage_target_pct=80.0,
            duplications_pct=job.duplications_pct,
            technical_debt_display=_format_technical_debt(job.technical_debt_minutes),
            maintainability_rating=None,
        ),
        priority_issues=priority_issues,
        risk_score=r_score,
        risk_score_version=r_version,
        open_findings=open_count,
        findings_by_severity=by_sev,
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _latest_completed_job(
    db: DbDep, project_id: uuid.UUID
) -> AnalysisJob | None:
    result = await db.execute(
        select(AnalysisJob)
        .where(
            AnalysisJob.project_id == project_id,
            AnalysisJob.status == "completed",
        )
        .order_by(AnalysisJob.completed_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _project_to_summary(project: Project, job: AnalysisJob | None) -> ProjectSummary:
    if job:
        gate_status = "Passed" if job.quality_gate_passed else "Failed"
        bugs = job.bugs_count
        vulns = job.vulnerabilities_count
        smells = job.code_smells_count
        coverage = _coverage_display(job.coverage_pct)
        last_analysis = _relative_time(job.completed_at)
        branch = job.source_branch or project.default_branch
        r_score: float | None = None  # populated on dashboard, not list view
    else:
        gate_status = "Unknown"
        bugs = vulns = smells = 0
        coverage = last_analysis = None
        branch = project.default_branch
        r_score = None

    return ProjectSummary(
        id=project.id,
        name=project.name,
        status=gate_status,
        bugs=bugs,
        vulnerabilities=vulns,
        code_smells=smells,
        coverage=coverage,
        last_analysis=last_analysis,
        branch=branch,
        source_type=project.source_type,
        archived=project.archived_at is not None,
        risk_score=r_score,
    )
