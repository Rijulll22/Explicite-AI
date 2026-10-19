"""
Analysis endpoints.

POST /projects/{project_id}/analyse   — submit ZIP, start job (202)
GET  /projects/{project_id}/analyse   — list jobs (most recent first)
GET  /projects/{project_id}/analyse/{job_id} — job status
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep, get_project_membership
from app.config import settings
from app.models.analysis import AnalysisJob
from app.schemas.analysis import AnalysisJobStatus
from app.schemas.auth import UserPreferences
from app.services.archive import ArchiveError, validate_and_extract
from app.services.job_runner import run_analysis_job

router = APIRouter(tags=["analysis"])


def _job_to_status(job: AnalysisJob) -> AnalysisJobStatus:
    total = (
        job.bugs_count
        + job.vulnerabilities_count
        + job.code_smells_count
        + job.security_hotspots_count
    )
    return AnalysisJobStatus(
        id=job.id,
        project_id=job.project_id,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        failed_at=job.failed_at,
        failure_reason=job.failure_reason,
        engine_name=job.engine_name,
        engine_version=job.engine_version,
        findings_count=total if job.status == "completed" else None,
        bugs_count=job.bugs_count,
        vulnerabilities_count=job.vulnerabilities_count,
        code_smells_count=job.code_smells_count,
        security_hotspots_count=job.security_hotspots_count,
    )


@router.post(
    "/projects/{project_id}/analyse",
    response_model=AnalysisJobStatus,
    status_code=202,
)
async def submit_analysis(
    project_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
    background_tasks: BackgroundTasks,
    source: UploadFile = File(..., description="ZIP archive of source files (max 10 MB)"),
) -> AnalysisJobStatus:
    """
    Accept a ZIP upload, validate it safely, and start an analysis job.
    Returns the queued job immediately (FR-AN-01: ≤ 1s response).
    Developer role or higher required.
    """
    project, _ = await get_project_membership(
        project_id, current_user, db, min_role="developer"
    )

    data = await source.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if len(data) > settings.MAX_UPLOAD_BYTES:
        mb_limit = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"Upload size {len(data) // 1024} KB exceeds {mb_limit} MB limit (FR-PROJ-02)",
        )

    job_id = uuid.uuid4()
    upload_base = Path(settings.UPLOAD_DIR) / str(project_id) / str(job_id)

    try:
        validate_and_extract(data, upload_base)
    except ArchiveError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    job = AnalysisJob(
        id=job_id,
        project_id=project_id,
        status="queued",
        source_branch=project.default_branch,
        source_path=str(upload_base),
    )
    db.add(job)
    await db.flush()
    # Commit before scheduling the background task — FastAPI runs background
    # tasks after the response is sent but before get_db's auto-commit, so
    # the runner would not find the job in the DB without this explicit commit.
    await db.commit()

    timeout = settings.ANALYSIS_TIMEOUT_SECONDS
    prefs = UserPreferences.model_validate(current_user.preferences or {})
    background_tasks.add_task(
        run_analysis_job,
        job_id,
        str(upload_base),
        timeout,
        prefs.quality_gate_max_bugs,
        prefs.quality_gate_max_vulnerabilities,
        prefs.quality_gate_coverage_threshold > 0,
        prefs.quality_gate_coverage_threshold,
    )

    return _job_to_status(job)


@router.get(
    "/projects/{project_id}/analyse",
    response_model=list[AnalysisJobStatus],
)
async def list_analysis_jobs(
    project_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> list[AnalysisJobStatus]:
    """List analysis jobs for the project, most recent first (max 20)."""
    await get_project_membership(project_id, current_user, db)

    result = await db.execute(
        select(AnalysisJob)
        .where(AnalysisJob.project_id == project_id)
        .order_by(AnalysisJob.created_at.desc())
        .limit(20)
    )
    return [_job_to_status(j) for j in result.scalars()]


@router.get(
    "/projects/{project_id}/analyse/{job_id}",
    response_model=AnalysisJobStatus,
)
async def get_analysis_job(
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> AnalysisJobStatus:
    """Retrieve the current status of a specific analysis job."""
    await get_project_membership(project_id, current_user, db)

    result = await db.execute(
        select(AnalysisJob).where(
            AnalysisJob.id == job_id,
            AnalysisJob.project_id == project_id,
        )
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Analysis job not found")

    return _job_to_status(job)
