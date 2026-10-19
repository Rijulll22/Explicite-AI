"""
Tests for GET /api/v1/projects/{id}/issues and
         GET /api/v1/projects/{id}/issues/{issue_id}.

Coverage:
- Unauthenticated → 401
- No analysis job → empty list
- All findings returned when no filters applied
- Filter by severity, type, status, and search query
- Invalid filter values → 422
- Combined filters are AND-ed
- Finding detail returned correctly
- Finding not found → 404
- Finding in wrong project → 404 (not 403, to avoid leaking existence)
- Non-member cannot access issues → 403
- Severity sort order: Critical before High
"""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.analysis import AnalysisJob
from app.models.finding import Finding
from app.models.project import Project, ProjectMembership
from app.models.user import User


def _make_finding(analysis_job, project, **kwargs) -> Finding:
    defaults = dict(
        id=uuid.uuid4(),
        analysis_job_id=analysis_job.id,
        project_id=project.id,
        engine_severity="Low",
        risk_level="Low",
        issue_type="Code Smell",
        title="Unused Variable",
        rule_key="java:S1481",
        file_path="Foo.java",
        line_number=10,
        status="Open",
    )
    defaults.update(kwargs)
    return Finding(**defaults)


@pytest.mark.asyncio
async def test_list_issues_unauthenticated(client: AsyncClient, project: Project):
    resp = await client.get(f"/api/v1/projects/{project.id}/issues")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_issues_no_job(
    client: AsyncClient, user: User, project: Project, auth_headers: dict
):
    resp = await client.get(
        f"/api/v1/projects/{project.id}/issues", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_list_issues_returns_all(
    client: AsyncClient,
    user: User,
    project: Project,
    analysis_job: AnalysisJob,
    finding: Finding,
    auth_headers: dict,
    db: AsyncSession,
):
    # Add a second finding
    f2 = _make_finding(analysis_job, project, title="Hard-coded Password", engine_severity="High")
    db.add(f2)
    await db.flush()

    resp = await client.get(
        f"/api/v1/projects/{project.id}/issues", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_filter_by_severity(
    client: AsyncClient,
    user: User,
    project: Project,
    analysis_job: AnalysisJob,
    finding: Finding,
    auth_headers: dict,
    db: AsyncSession,
):
    f2 = _make_finding(analysis_job, project, engine_severity="Low", title="Low Issue")
    db.add(f2)
    await db.flush()

    resp = await client.get(
        f"/api/v1/projects/{project.id}/issues",
        params={"severity": "Critical"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(i["severity"] == "Critical" for i in items)
    assert any(i["title"] == "SQL Injection" for i in items)


@pytest.mark.asyncio
async def test_filter_by_type(
    client: AsyncClient,
    user: User,
    project: Project,
    analysis_job: AnalysisJob,
    finding: Finding,  # Vulnerability
    auth_headers: dict,
    db: AsyncSession,
):
    f2 = _make_finding(
        analysis_job,
        project,
        issue_type="Code Smell",
        engine_severity="Low",
        title="Smell",
    )
    db.add(f2)
    await db.flush()

    resp = await client.get(
        f"/api/v1/projects/{project.id}/issues",
        params={"type": "Vulnerability"},
        headers=auth_headers,
    )
    items = resp.json()["items"]
    assert all(i["type"] == "Vulnerability" for i in items)
    assert len(items) == 1


@pytest.mark.asyncio
async def test_filter_by_status(
    client: AsyncClient,
    user: User,
    project: Project,
    analysis_job: AnalysisJob,
    finding: Finding,  # Open
    auth_headers: dict,
    db: AsyncSession,
):
    f2 = _make_finding(
        analysis_job,
        project,
        status="Resolved",
        engine_severity="Low",
        title="Resolved Issue",
    )
    db.add(f2)
    await db.flush()

    resp = await client.get(
        f"/api/v1/projects/{project.id}/issues",
        params={"status": "Resolved"},
        headers=auth_headers,
    )
    items = resp.json()["items"]
    assert all(i["status"] == "Resolved" for i in items)
    assert len(items) == 1


@pytest.mark.asyncio
async def test_filter_by_search_title(
    client: AsyncClient,
    user: User,
    project: Project,
    analysis_job: AnalysisJob,
    finding: Finding,  # "SQL Injection"
    auth_headers: dict,
    db: AsyncSession,
):
    f2 = _make_finding(
        analysis_job, project, engine_severity="Low", title="Unused Import"
    )
    db.add(f2)
    await db.flush()

    resp = await client.get(
        f"/api/v1/projects/{project.id}/issues",
        params={"q": "sql"},
        headers=auth_headers,
    )
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "SQL Injection"


@pytest.mark.asyncio
async def test_filter_by_search_file(
    client: AsyncClient,
    user: User,
    project: Project,
    analysis_job: AnalysisJob,
    finding: Finding,  # file_path="StudentDAO.java"
    auth_headers: dict,
):
    resp = await client.get(
        f"/api/v1/projects/{project.id}/issues",
        params={"q": "studentdao"},
        headers=auth_headers,
    )
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["file"] == "StudentDAO.java"


@pytest.mark.asyncio
async def test_combined_filters(
    client: AsyncClient,
    user: User,
    project: Project,
    analysis_job: AnalysisJob,
    finding: Finding,  # Critical, Vulnerability, Open
    auth_headers: dict,
    db: AsyncSession,
):
    f2 = _make_finding(
        analysis_job,
        project,
        engine_severity="Critical",
        issue_type="Bug",
        status="Open",
        title="NullPtr",
    )
    db.add(f2)
    await db.flush()

    # Only Critical Vulnerabilities
    resp = await client.get(
        f"/api/v1/projects/{project.id}/issues",
        params={"severity": "Critical", "type": "Vulnerability"},
        headers=auth_headers,
    )
    items = resp.json()["items"]
    assert all(i["severity"] == "Critical" and i["type"] == "Vulnerability" for i in items)
    assert len(items) == 1


@pytest.mark.asyncio
async def test_invalid_severity_filter(
    client: AsyncClient, user: User, project: Project, auth_headers: dict
):
    resp = await client.get(
        f"/api/v1/projects/{project.id}/issues",
        params={"severity": "INVALID"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_severity_sort_order(
    client: AsyncClient,
    user: User,
    project: Project,
    analysis_job: AnalysisJob,
    db: AsyncSession,
    auth_headers: dict,
):
    """Critical findings must appear before High findings."""
    severities = ["Low", "Medium", "High", "Critical"]
    for sev in severities:
        db.add(_make_finding(analysis_job, project, engine_severity=sev, title=f"{sev} issue"))
    await db.flush()

    resp = await client.get(
        f"/api/v1/projects/{project.id}/issues", headers=auth_headers
    )
    items = resp.json()["items"]
    order = [i["severity"] for i in items]
    assert order.index("Critical") < order.index("High")
    assert order.index("High") < order.index("Medium")
    assert order.index("Medium") < order.index("Low")


@pytest.mark.asyncio
async def test_get_issue_detail(
    client: AsyncClient,
    user: User,
    project: Project,
    finding: Finding,
    auth_headers: dict,
):
    resp = await client.get(
        f"/api/v1/projects/{project.id}/issues/{finding.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "SQL Injection"
    assert data["severity"] == "Critical"
    assert data["cwe_id"] == "CWE-89"
    assert data["cvss_score"] == pytest.approx(9.1)
    assert "password_hash" not in str(data)


@pytest.mark.asyncio
async def test_get_issue_not_found(
    client: AsyncClient, user: User, project: Project, auth_headers: dict
):
    resp = await client.get(
        f"/api/v1/projects/{project.id}/issues/{uuid.uuid4()}",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_issue_wrong_project(
    client: AsyncClient,
    user: User,
    project: Project,
    finding: Finding,
    second_user: User,
    db: AsyncSession,
):
    """An issue that belongs to a different project returns 404, not 403."""
    other_project = Project(
        id=uuid.uuid4(),
        name="Other",
        default_branch="main",
        owner_id=second_user.id,
    )
    db.add(other_project)
    db.add(
        ProjectMembership(
            project_id=other_project.id, user_id=user.id, role="developer"
        )
    )
    await db.flush()

    token = create_access_token(subject=str(user.id))
    resp = await client.get(
        f"/api/v1/projects/{other_project.id}/issues/{finding.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_issues_non_member_forbidden(
    client: AsyncClient,
    second_user: User,
    project: Project,
):
    token = create_access_token(subject=str(second_user.id))
    resp = await client.get(
        f"/api/v1/projects/{project.id}/issues",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
