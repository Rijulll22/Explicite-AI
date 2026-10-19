"""
Tests for POST /api/v1/projects (project creation).

Coverage:
- Create project → 201 with ProjectSummary (Unknown status, no analysis)
- Missing / empty name → 422
- Name too long → 422
- Unauthenticated → 401
- New project appears in GET /projects for owner
- New project not visible to another user (project isolation)
- Default branch defaults to "main" when omitted
- Custom branch is preserved
- Owner membership created automatically (owner can GET dashboard immediately)
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.project import Project, ProjectMembership
from app.models.user import User


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _create(client: AsyncClient, headers: dict, payload: dict):
    return await client.post("/api/v1/projects", json=payload, headers=headers)


# ── Success cases ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_project_minimal(client: AsyncClient, auth_headers: dict):
    resp = await _create(client, auth_headers, {"name": "My New Project"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My New Project"
    assert data["status"] == "Unknown"
    assert data["branch"] == "main"
    assert data["bugs"] == 0
    assert data["archived"] is False
    assert "id" in data
    assert "password" not in str(data)


@pytest.mark.asyncio
async def test_create_project_custom_branch(client: AsyncClient, auth_headers: dict):
    resp = await _create(client, auth_headers, {"name": "Feature", "default_branch": "develop"})
    assert resp.status_code == 201
    assert resp.json()["branch"] == "develop"


@pytest.mark.asyncio
async def test_create_project_with_description(client: AsyncClient, auth_headers: dict):
    resp = await _create(client, auth_headers, {"name": "Described", "description": "A test project"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Described"


@pytest.mark.asyncio
async def test_create_project_appears_in_list(client: AsyncClient, auth_headers: dict):
    await _create(client, auth_headers, {"name": "Listed Project"})
    resp = await client.get("/api/v1/projects", headers=auth_headers)
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()}
    assert "Listed Project" in names


@pytest.mark.asyncio
async def test_create_project_owner_can_open_dashboard(
    client: AsyncClient, auth_headers: dict
):
    """Dashboard endpoint should succeed immediately with no-analysis state."""
    create_resp = await _create(client, auth_headers, {"name": "Dashboard Test"})
    proj_id = create_resp.json()["id"]
    dash_resp = await client.get(f"/api/v1/projects/{proj_id}/dashboard", headers=auth_headers)
    assert dash_resp.status_code == 200
    data = dash_resp.json()
    assert data["project_name"] == "Dashboard Test"
    assert data["quality_gate"]["passed"] is False


@pytest.mark.asyncio
async def test_create_project_branch_defaults_to_main(client: AsyncClient, auth_headers: dict):
    resp = await _create(client, auth_headers, {"name": "No Branch"})
    assert resp.json()["branch"] == "main"


@pytest.mark.asyncio
async def test_create_two_projects_same_name_allowed(client: AsyncClient, auth_headers: dict):
    """Duplicate project names are permitted (no unique constraint on name)."""
    r1 = await _create(client, auth_headers, {"name": "Duplicate"})
    r2 = await _create(client, auth_headers, {"name": "Duplicate"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]


# ── Validation failures ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_project_empty_name(client: AsyncClient, auth_headers: dict):
    resp = await _create(client, auth_headers, {"name": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_project_whitespace_name(client: AsyncClient, auth_headers: dict):
    resp = await _create(client, auth_headers, {"name": "   "})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_project_name_too_long(client: AsyncClient, auth_headers: dict):
    resp = await _create(client, auth_headers, {"name": "x" * 256})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_project_missing_name(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/projects", json={}, headers=auth_headers)
    assert resp.status_code == 422


# ── Auth enforcement ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_project_unauthenticated(client: AsyncClient):
    resp = await _create(client, {}, {"name": "No Auth"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_project_invalid_token(client: AsyncClient):
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "Bad Token"},
        headers={"Authorization": "Bearer notavalidtoken"},
    )
    assert resp.status_code == 401


# ── Project isolation ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_project_not_visible_to_other_user(
    client: AsyncClient, auth_headers: dict, second_user: User
):
    """A project owned by user A must not appear in user B's project list."""
    await _create(client, auth_headers, {"name": "Owner Only Project"})
    other_token = create_access_token(subject=str(second_user.id))
    other_headers = {"Authorization": f"Bearer {other_token}"}
    resp = await client.get("/api/v1/projects", headers=other_headers)
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()}
    assert "Owner Only Project" not in names


@pytest.mark.asyncio
async def test_dashboard_forbidden_for_non_member(
    client: AsyncClient, auth_headers: dict, second_user: User
):
    """User B cannot access user A's project dashboard."""
    create_resp = await _create(client, auth_headers, {"name": "Private Project"})
    proj_id = create_resp.json()["id"]
    other_token = create_access_token(subject=str(second_user.id))
    other_headers = {"Authorization": f"Bearer {other_token}"}
    resp = await client.get(f"/api/v1/projects/{proj_id}/dashboard", headers=other_headers)
    assert resp.status_code == 403


# ── Risk score integration tests ──────────────────────────────────────────────

from datetime import datetime, timezone

from app.models.analysis import AnalysisJob
from app.models.finding import Finding


@pytest.mark.asyncio
async def test_dashboard_no_analysis_risk_score_is_none(
    client: AsyncClient, auth_headers: dict
):
    """Dashboard with no analysis returns risk_score=None and no-analysis gate."""
    resp = await _create(client, auth_headers, {"name": "Risk Score None"})
    proj_id = resp.json()["id"]
    dash = await client.get(f"/api/v1/projects/{proj_id}/dashboard", headers=auth_headers)
    assert dash.status_code == 200
    data = dash.json()
    assert data["risk_score"] is None
    assert data["risk_score_version"] is None
    assert data["open_findings"] == 0
    assert data["findings_by_severity"] == {}
    assert data["quality_gate"]["passed"] is False
    assert "No analysis" in data["quality_gate"]["failed_conditions"][0]


@pytest.mark.asyncio
async def test_dashboard_with_findings_returns_risk_score(
    client: AsyncClient,
    auth_headers: dict,
    db: AsyncSession,
    user: User,
    project: Project,
    analysis_job: AnalysisJob,
    finding: Finding,
):
    """
    Dashboard with real findings returns a non-None risk_score, the correct
    open_findings count, and findings_by_severity breakdown.
    """
    dash = await client.get(
        f"/api/v1/projects/{project.id}/dashboard", headers=auth_headers
    )
    assert dash.status_code == 200
    data = dash.json()

    # risk_score should be a float between 0 and 100
    assert data["risk_score"] is not None
    assert 0.0 <= data["risk_score"] <= 100.0
    assert data["risk_score_version"] == "v1.0"

    # The one finding (Critical, Open) contributes to open_findings
    assert data["open_findings"] == 1
    assert data["findings_by_severity"].get("Critical", 0) == 1


@pytest.mark.asyncio
async def test_dashboard_resolved_finding_reduces_open_count(
    client: AsyncClient,
    auth_headers: dict,
    db: AsyncSession,
    user: User,
    project: Project,
    analysis_job: AnalysisJob,
    finding: Finding,
):
    """Resolving the finding drops open_findings to 0 but does not affect risk_score_version."""
    finding.status = "Resolved"
    db.add(finding)
    await db.flush()

    dash = await client.get(
        f"/api/v1/projects/{project.id}/dashboard", headers=auth_headers
    )
    assert dash.status_code == 200
    data = dash.json()
    assert data["open_findings"] == 0
    # risk_score still reflects resolved finding counted (0 unresolved → 0.0)
    assert data["risk_score"] == 0.0


@pytest.mark.asyncio
async def test_dashboard_quality_gate_conditions_use_service(
    client: AsyncClient,
    auth_headers: dict,
    user: User,
    project: Project,
    analysis_job: AnalysisJob,
):
    """
    Dashboard quality gate conditions come from quality_gate service.
    analysis_job has bugs_count=3 and vulnerabilities_count=1, so both fail.
    """
    dash = await client.get(
        f"/api/v1/projects/{project.id}/dashboard", headers=auth_headers
    )
    assert dash.status_code == 200
    data = dash.json()
    gate = data["quality_gate"]
    assert gate["passed"] is False
    # Both bugs and vulnerabilities should appear in the conditions
    conds = " ".join(gate["failed_conditions"]).lower()
    assert "bug" in conds
    assert "vulnerabilit" in conds


@pytest.mark.asyncio
async def test_dashboard_uses_latest_completed_not_failed_job(
    client: AsyncClient,
    auth_headers: dict,
    db: AsyncSession,
    user: User,
    project: Project,
    analysis_job: AnalysisJob,
    finding: Finding,
):
    """
    If a newer job exists but has failed, dashboard should still use the
    latest *completed* job, not the failed one.
    """
    # Insert a newer failed job
    failed_job = AnalysisJob(
        id=uuid.uuid4(),
        project_id=project.id,
        status="failed",
        failure_reason="semgrep timeout",
        failed_at=datetime.now(tz=timezone.utc),
    )
    db.add(failed_job)
    await db.flush()

    dash = await client.get(
        f"/api/v1/projects/{project.id}/dashboard", headers=auth_headers
    )
    assert dash.status_code == 200
    data = dash.json()
    # Dashboard should reflect the original completed job, not the failed one
    assert str(data["analysis_job_id"]) == str(analysis_job.id)
    assert data["metrics"]["bugs"] == analysis_job.bugs_count
