import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbDep, get_project_membership
from app.models.analysis import AnalysisJob
from app.models.finding import Finding
from app.schemas.finding import FindingDetail, FindingListResponse, FindingSummary, FindingStatusUpdate, SourceExcerptResponse

router = APIRouter(tags=["issues"])

_VALID_SEVERITIES = {"Critical", "High", "Medium", "Low"}
_VALID_TYPES = {"Vulnerability", "Bug", "Code Smell", "Security Hotspot"}
_VALID_STATUSES = {"Open", "In Review", "Resolved"}
_SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


@router.get(
    "/projects/{project_id}/issues",
    response_model=FindingListResponse,
)
async def list_issues(
    project_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
    severity: Annotated[str | None, Query(description="Critical | High | Medium | Low")] = None,
    type: Annotated[  # noqa: A002 — mirrors frontend query param name
        str | None,
        Query(description="Vulnerability | Bug | Code Smell | Security Hotspot"),
    ] = None,
    status: Annotated[  # noqa: A002 — mirrors frontend query param name
        str | None,
        Query(description="Open | In Review | Resolved"),
    ] = None,
    q: Annotated[str | None, Query(description="Search in title and file path")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> FindingListResponse:
    """
    List findings for a project.

    Findings come from the **latest completed** analysis job.
    All filters are AND-combined. Searching matches any substring in title
    or file path (case-insensitive).
    Results are sorted by severity (Critical first) then by title.
    """
    await get_project_membership(project_id, current_user, db)

    # Validate filter values (return 422 on unknown values so the client can diagnose)
    if severity and severity not in _VALID_SEVERITIES:
        raise HTTPException(
            status_code=422,
            detail=f"severity must be one of {sorted(_VALID_SEVERITIES)}",
        )
    if type and type not in _VALID_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"type must be one of {sorted(_VALID_TYPES)}",
        )
    if status and status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"status must be one of {sorted(_VALID_STATUSES)}",
        )

    # Locate the latest completed job for this project
    job_result = await db.execute(
        select(AnalysisJob)
        .where(
            AnalysisJob.project_id == project_id,
            AnalysisJob.status == "completed",
        )
        .order_by(AnalysisJob.completed_at.desc())
        .limit(1)
    )
    job = job_result.scalar_one_or_none()

    if job is None:
        return FindingListResponse(total=0, skip=skip, limit=limit, items=[])

    # Build the filtered query
    stmt = select(Finding).where(Finding.analysis_job_id == job.id)

    if severity:
        stmt = stmt.where(Finding.engine_severity == severity)
    if type:
        stmt = stmt.where(Finding.issue_type == type)
    if status:
        stmt = stmt.where(Finding.status == status)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            Finding.title.ilike(pattern) | Finding.file_path.ilike(pattern)
        )

    # Total count (before pagination)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Paginated results
    results = await db.execute(stmt.offset(skip).limit(limit))
    findings = results.scalars().all()

    # Sort by severity order in Python (avoids complex DB expressions)
    findings = sorted(
        findings, key=lambda f: (_SEVERITY_ORDER.get(f.engine_severity, 99), f.title)
    )

    items = [
        FindingSummary(
            id=f.id,
            severity=f.engine_severity,
            type=f.issue_type,
            title=f.title,
            rule=f.rule_key,
            file=f.file_path,
            line=f.line_number,
            risk=f.risk_level,
            status=f.status,
            created_at=f.created_at,
        )
        for f in findings
    ]
    return FindingListResponse(total=total, skip=skip, limit=limit, items=items)


@router.get(
    "/projects/{project_id}/issues/{issue_id}",
    response_model=FindingDetail,
)
async def get_issue(
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> FindingDetail:
    """Return full detail for a single finding, including AI explanation if available."""
    await get_project_membership(project_id, current_user, db)

    result = await db.execute(
        select(Finding).where(
            Finding.id == issue_id,
            Finding.project_id == project_id,
        )
    )
    finding = result.scalar_one_or_none()
    if finding is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    return FindingDetail(
        id=finding.id,
        severity=finding.engine_severity,
        type=finding.issue_type,
        title=finding.title,
        rule=finding.rule_key,
        file=finding.file_path,
        line=finding.line_number,
        risk=finding.risk_level,
        risk_score=finding.risk_score,
        risk_score_version=finding.risk_score_version,
        status=finding.status,
        description=finding.description,
        ai_explanation=finding.ai_explanation,
        cwe_id=finding.cwe_id,
        owasp_category=finding.owasp_category,
        cvss_score=finding.cvss_score,
        cvss_vector=finding.cvss_vector,
        cvss_version=finding.cvss_version,
        cvss_severity=None,
        analysis_job_id=finding.analysis_job_id,
        created_at=finding.created_at,
        updated_at=finding.updated_at,
    )


def _finding_to_detail(finding: Finding) -> FindingDetail:
    return FindingDetail(
        id=finding.id,
        severity=finding.engine_severity,
        type=finding.issue_type,
        title=finding.title,
        rule=finding.rule_key,
        file=finding.file_path,
        line=finding.line_number,
        risk=finding.risk_level,
        risk_score=finding.risk_score,
        risk_score_version=finding.risk_score_version,
        status=finding.status,
        description=finding.description,
        ai_explanation=finding.ai_explanation,
        cwe_id=finding.cwe_id,
        owasp_category=finding.owasp_category,
        cvss_score=finding.cvss_score,
        cvss_vector=finding.cvss_vector,
        cvss_version=finding.cvss_version,
        cvss_severity=None,
        analysis_job_id=finding.analysis_job_id,
        created_at=finding.created_at,
        updated_at=finding.updated_at,
    )


@router.patch(
    "/projects/{project_id}/issues/{issue_id}",
    response_model=FindingDetail,
)
async def update_issue_status(
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    body: FindingStatusUpdate,
    current_user: CurrentUser,
    db: DbDep,
) -> FindingDetail:
    """Update the status of a single finding. Requires project membership."""
    await get_project_membership(project_id, current_user, db)

    result = await db.execute(
        select(Finding).where(
            Finding.id == issue_id,
            Finding.project_id == project_id,
        )
    )
    finding = result.scalar_one_or_none()
    if finding is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    finding.status = body.status
    db.add(finding)
    await db.flush()
    await db.refresh(finding)

    return _finding_to_detail(finding)


@router.get(
    "/projects/{project_id}/issues/{issue_id}/source",
    response_model=SourceExcerptResponse,
)
async def get_issue_source(
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
    context_lines: int = 10,
) -> SourceExcerptResponse:
    """
    Return a bounded source excerpt (±context_lines) around the finding's line.

    Authentication and project membership are required.
    The source_path is never exposed in the response.
    Returns available=False when source files are unavailable.
    """
    await get_project_membership(project_id, current_user, db)

    finding_result = await db.execute(
        select(Finding).where(
            Finding.id == issue_id,
            Finding.project_id == project_id,
        )
    )
    finding = finding_result.scalar_one_or_none()
    if finding is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    # Load the analysis job to get the source_path (never surfaced in response)
    job_result = await db.execute(
        select(AnalysisJob).where(AnalysisJob.id == finding.analysis_job_id)
    )
    job = job_result.scalar_one_or_none()

    if job is None or not job.source_path:
        return SourceExcerptResponse(
            available=False,
            file=finding.file_path or "",
            target_line=finding.line_number,
            lines=[],
            message="Source files are not available for this analysis.",
        )

    from app.services.source_reader import read_source_excerpt
    context_lines = max(1, min(context_lines, 30))
    excerpt = read_source_excerpt(
        source_dir=job.source_path,
        relative_file_path=finding.file_path,
        target_line=finding.line_number,
        context_lines=context_lines,
    )

    return SourceExcerptResponse(
        available=excerpt.available,
        file=excerpt.file,
        target_line=excerpt.target_line,
        lines=[
            {"number": ln.number, "content": ln.content, "is_target": ln.is_target}
            for ln in excerpt.lines
        ],
        message=excerpt.message,
    )
