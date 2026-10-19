"""
Suggested-fix endpoints (SRS FR-FIX-01 – FR-FIX-07).

POST   /projects/{project_id}/issues/{issue_id}/fix        generate fix
GET    /projects/{project_id}/fixes/{fix_id}               get fix detail
POST   /projects/{project_id}/fixes/{fix_id}/approve       approve fix
POST   /projects/{project_id}/fixes/{fix_id}/reject        reject fix
GET    /projects/{project_id}/fixes/{fix_id}/download      download patched ZIP

Authentication and project membership are enforced on every endpoint.
Original source files are NEVER written; the download endpoint streams
a patched ZIP built in memory.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbDep, get_project_membership
from app.models.analysis import AnalysisJob
from app.models.finding import Finding
from app.models.suggested_fix import SuggestedFix
from app.schemas.suggested_fix import FixResponse, FixSummary
from app.services.ai_service import (
    AiInvalidResponseError,
    AiUnavailableError,
    FixContext,
    get_provider,
)
from app.services.fix_service import (
    SourceUnavailableError,
    StaleFixError,
    compute_unified_diff,
    create_patched_zip,
    extract_source_context,
)

router = APIRouter(tags=["fixes"])

_VALID_STATUSES = {"proposed", "approved", "rejected", "applied", "failed", "stale"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fix_to_response(fix: SuggestedFix) -> FixResponse:
    return FixResponse(
        id=fix.id,
        finding_id=fix.finding_id,
        project_id=fix.project_id,
        analysis_job_id=fix.analysis_job_id,
        target_file=fix.target_file,
        original_snippet=fix.original_snippet,
        proposed_snippet=fix.proposed_snippet,
        unified_diff=fix.unified_diff,
        snippet_start_line=fix.snippet_start_line,
        snippet_end_line=fix.snippet_end_line,
        rationale=fix.rationale,
        caveats=fix.caveats,
        status=fix.status,
        source_available=fix.source_available,
        model_provider=fix.model_provider,
        model_name=fix.model_name,
        created_at=fix.created_at,
        updated_at=fix.updated_at,
        approved_at=fix.approved_at,
        rejected_at=fix.rejected_at,
        applied_at=fix.applied_at,
    )


async def _load_fix_for_project(
    fix_id: uuid.UUID,
    project_id: uuid.UUID,
    db,
) -> SuggestedFix:
    """Load a fix and verify it belongs to the given project."""
    result = await db.execute(
        select(SuggestedFix).where(
            SuggestedFix.id == fix_id,
            SuggestedFix.project_id == project_id,
        )
    )
    fix = result.scalar_one_or_none()
    if fix is None:
        raise HTTPException(status_code=404, detail="Suggested fix not found.")
    return fix


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/projects/{project_id}/issues/{issue_id}/fix",
    response_model=FixResponse,
    status_code=201,
)
async def generate_fix(
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> FixResponse:
    """
    Generate an AI-proposed fix for a finding.

    Returns 503 when no AI model is configured.
    Returns 409 when source code is not available.
    The original source directory is never modified during generation.
    """
    await get_project_membership(project_id, current_user, db)

    # Load finding with project membership verification
    result = await db.execute(
        select(Finding).where(
            Finding.id == issue_id,
            Finding.project_id == project_id,
        )
    )
    finding = result.scalar_one_or_none()
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found.")

    # Load the most recent completed job for this finding's analysis
    job_result = await db.execute(
        select(AnalysisJob).where(AnalysisJob.id == finding.analysis_job_id)
    )
    job = job_result.scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=409, detail="Analysis job for this finding is missing."
        )

    # Extract source context (safe, bounded, path-validated)
    source_ctx = None
    source_available = False
    try:
        source_ctx = extract_source_context(
            job.source_path,
            finding.file_path,
            finding.line_number,
        )
        source_available = True
    except SourceUnavailableError:
        pass   # AI will be asked to propose a generic fix without source

    # Build FixContext for the AI
    fix_ctx = FixContext(
        rule_key=finding.rule_key,
        title=finding.title or "",
        file_path=finding.file_path,
        line_number=finding.line_number,
        engine_severity=finding.engine_severity or "Unknown",
        risk_level=finding.risk_level or "Unknown",
        description=finding.description,
        cwe_id=finding.cwe_id,
        owasp_category=finding.owasp_category,
        snippet=source_ctx.snippet if source_ctx else None,
        snippet_start_line=source_ctx.snippet_start_line if source_ctx else None,
        snippet_end_line=source_ctx.snippet_end_line if source_ctx else None,
    )

    try:
        fix_result = await get_provider().generate_fix(fix_ctx)
    except AiUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except AiInvalidResponseError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI returned an unreadable fix proposal: {exc}",
        )

    # Compute proposed snippet and unified diff
    proposed_snippet: str | None = None
    unified_diff: str | None = None
    original_snippet: str | None = None
    snippet_start: int | None = None
    snippet_end: int | None = None
    original_hash: str | None = None
    target_file: str | None = finding.file_path

    if source_ctx is not None and fix_result.proposed_lines:
        original_snippet = source_ctx.snippet
        proposed_snippet = "\n".join(fix_result.proposed_lines)
        unified_diff = compute_unified_diff(
            original_snippet,
            proposed_snippet,
            finding.file_path or "unknown",
        )
        snippet_start = source_ctx.snippet_start_line
        snippet_end = source_ctx.snippet_end_line
        original_hash = source_ctx.content_hash

    fix = SuggestedFix(
        finding_id=finding.id,
        project_id=project_id,
        analysis_job_id=finding.analysis_job_id,
        target_file=target_file,
        original_hash=original_hash,
        original_snippet=original_snippet,
        proposed_snippet=proposed_snippet,
        unified_diff=unified_diff,
        snippet_start_line=snippet_start,
        snippet_end_line=snippet_end,
        rationale=fix_result.rationale,
        caveats=fix_result.caveats,
        status="proposed",
        source_available=source_available,
        model_provider=fix_result.model_provider,
        model_name=fix_result.model_name,
    )
    db.add(fix)
    await db.flush()

    return _fix_to_response(fix)


@router.get(
    "/projects/{project_id}/fixes/{fix_id}",
    response_model=FixResponse,
)
async def get_fix(
    project_id: uuid.UUID,
    fix_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> FixResponse:
    """Return full detail for a suggested fix, including diff."""
    await get_project_membership(project_id, current_user, db)
    fix = await _load_fix_for_project(fix_id, project_id, db)
    return _fix_to_response(fix)


@router.get(
    "/projects/{project_id}/issues/{issue_id}/fixes",
    response_model=list[FixSummary],
)
async def list_fixes_for_issue(
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> list[FixSummary]:
    """List all fix proposals for a finding, most recent first."""
    await get_project_membership(project_id, current_user, db)

    # Verify finding belongs to project
    result = await db.execute(
        select(Finding).where(
            Finding.id == issue_id,
            Finding.project_id == project_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Finding not found.")

    fixes_result = await db.execute(
        select(SuggestedFix)
        .where(
            SuggestedFix.finding_id == issue_id,
            SuggestedFix.project_id == project_id,
        )
        .order_by(SuggestedFix.created_at.desc())
        .limit(20)
    )
    return [
        FixSummary(
            id=f.id,
            finding_id=f.finding_id,
            status=f.status,
            target_file=f.target_file,
            model_provider=f.model_provider,
            model_name=f.model_name,
            created_at=f.created_at,
        )
        for f in fixes_result.scalars()
    ]


@router.post(
    "/projects/{project_id}/fixes/{fix_id}/approve",
    response_model=FixResponse,
)
async def approve_fix(
    project_id: uuid.UUID,
    fix_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> FixResponse:
    """
    Explicitly approve a proposed fix (FR-FIX-04).

    Only the project owner or developer role may approve.
    The fix must be in 'proposed' status.
    Stale detection runs at approval time — if the source file's hash
    no longer matches, the fix is automatically marked stale and a 409
    is returned.
    """
    _, role = await get_project_membership(
        project_id, current_user, db, min_role="developer"
    )

    fix = await _load_fix_for_project(fix_id, project_id, db)

    if fix.status != "proposed":
        raise HTTPException(
            status_code=409,
            detail=f"Fix is in '{fix.status}' status; only 'proposed' fixes can be approved.",
        )

    # Stale detection (FR-FIX-06): verify source hash before approval
    if fix.original_hash and fix.target_file:
        job_result = await db.execute(
            select(AnalysisJob).where(AnalysisJob.id == fix.analysis_job_id)
        )
        job = job_result.scalar_one_or_none()

        if job and job.source_path:
            try:
                current_ctx = extract_source_context(
                    job.source_path,
                    fix.target_file,
                    None,
                )
                if current_ctx.content_hash != fix.original_hash:
                    fix.status = "stale"
                    fix.updated_at = datetime.now(timezone.utc)
                    db.add(fix)
                    await db.flush()
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "The source file has changed since this fix was generated. "
                            "The fix has been marked stale. Generate a new fix."
                        ),
                    )
            except SourceUnavailableError:
                pass   # Can't verify — allow approval to proceed

    fix.status = "approved"
    fix.approved_at = datetime.now(timezone.utc)
    fix.updated_at = fix.approved_at
    db.add(fix)
    await db.flush()

    return _fix_to_response(fix)


@router.post(
    "/projects/{project_id}/fixes/{fix_id}/reject",
    response_model=FixResponse,
)
async def reject_fix(
    project_id: uuid.UUID,
    fix_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> FixResponse:
    """
    Reject a proposed or approved fix.
    Developer role or higher required.
    """
    await get_project_membership(project_id, current_user, db, min_role="developer")

    fix = await _load_fix_for_project(fix_id, project_id, db)

    if fix.status in {"rejected", "applied"}:
        raise HTTPException(
            status_code=409,
            detail=f"Fix is already in '{fix.status}' status.",
        )

    fix.status = "rejected"
    fix.rejected_at = datetime.now(timezone.utc)
    fix.updated_at = fix.rejected_at
    db.add(fix)
    await db.flush()

    return _fix_to_response(fix)


@router.get(
    "/projects/{project_id}/fixes/{fix_id}/download",
)
async def download_patched_zip(
    project_id: uuid.UUID,
    fix_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> Response:
    """
    Download a ZIP archive containing the patched source (FR-FIX-07).

    Only approved fixes can be downloaded.
    Stale detection runs immediately before patching — if the source hash
    no longer matches, the fix is marked stale and a 409 is returned.
    The original source_path directory is NEVER modified.
    Marks the fix as 'applied' on success.
    """
    await get_project_membership(project_id, current_user, db)

    fix = await _load_fix_for_project(fix_id, project_id, db)

    if fix.status != "approved":
        raise HTTPException(
            status_code=409,
            detail=f"Fix is in '{fix.status}' status; only 'approved' fixes can be downloaded.",
        )

    if not fix.source_available or fix.original_snippet is None:
        raise HTTPException(
            status_code=409,
            detail="Source was not available when this fix was generated; no ZIP can be produced.",
        )

    job_result = await db.execute(
        select(AnalysisJob).where(AnalysisJob.id == fix.analysis_job_id)
    )
    job = job_result.scalar_one_or_none()

    if not job or not job.source_path:
        raise HTTPException(
            status_code=409,
            detail="Source directory reference is missing; cannot produce a patched ZIP.",
        )

    try:
        zip_bytes = create_patched_zip(
            source_dir=job.source_path,
            target_file=fix.target_file or "",
            original_hash=fix.original_hash or "",
            original_snippet=fix.original_snippet or "",
            proposed_snippet=fix.proposed_snippet or "",
        )
    except StaleFixError as exc:
        fix.status = "stale"
        fix.updated_at = datetime.now(timezone.utc)
        db.add(fix)
        await db.flush()
        raise HTTPException(status_code=409, detail=str(exc))
    except SourceUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    # Mark applied
    fix.status = "applied"
    fix.applied_at = datetime.now(timezone.utc)
    fix.updated_at = fix.applied_at
    db.add(fix)
    await db.flush()

    filename = f"fix-{fix.id}.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
