"""
Tests for PATCH /api/v1/projects/{project_id}/issues/{issue_id}.

Coverage:
- Successful status update → 200 with FindingDetail
- Persistence: re-fetching the issue via GET reflects the new status
- All three valid status values accepted (Open, In Review, Resolved)
- Invalid status → 422
- Unauthenticated → 401
- Invalid/expired token → 401
- Nonexistent issue in known project → 404
- Issue belongs to a different project → 404
- No project membership → 403
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.analysis import AnalysisJob
from app.models.finding import Finding
from app.models.project import Project, ProjectMembership
from app.models.user import User


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _patch_status(
    client: AsyncClient,
    headers: dict,
    project_id: str,
    issue_id: str,
    status: str,
):
    return await client.patch(
        f"/api/v1/projects/{project_id}/issues/{issue_id}",
        json={"status": status},
        headers=headers,
    )


# ── Success cases ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_status_success(
    client: AsyncClient,
    auth_headers: dict,
    project: Project,
    finding: Finding,
):
    resp = await _patch_status(
        client, auth_headers, str(project.id), str(finding.id), "In Review"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "In Review"
    assert data["id"] == str(finding.id)
    assert "password" not in str(data)


@pytest.mark.asyncio
async def test_update_status_persisted(
    client: AsyncClient,
    auth_headers: dict,
    project: Project,
    finding: Finding,
):
    """Re-fetching the issue after PATCH must return the new status."""
    await _patch_status(
        client, auth_headers, str(project.id), str(finding.id), "Resolved"
    )
    get_resp = await client.get(
        f"/api/v1/projects/{project.id}/issues/{finding.id}",
        headers=auth_headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "Resolved"


@pytest.mark.asyncio
async def test_update_status_to_open(
    client: AsyncClient,
    auth_headers: dict,
    project: Project,
    finding: Finding,
):
    resp = await _patch_status(
        client, auth_headers, str(project.id), str(finding.id), "Open"
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "Open"


@pytest.mark.asyncio
async def test_update_status_to_in_review(
    client: AsyncClient,
    auth_headers: dict,
    project: Project,
    finding: Finding,
):
    resp = await _patch_status(
        client, auth_headers, str(project.id), str(finding.id), "In Review"
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "In Review"


@pytest.mark.asyncio
async def test_update_status_to_resolved(
    client: AsyncClient,
    auth_headers: dict,
    project: Project,
    finding: Finding,
):
    resp = await _patch_status(
        client, auth_headers, str(project.id), str(finding.id), "Resolved"
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "Resolved"


# ── Validation failures ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_status_invalid_value(
    client: AsyncClient,
    auth_headers: dict,
    project: Project,
    finding: Finding,
):
    resp = await _patch_status(
        client, auth_headers, str(project.id), str(finding.id), "Closed"
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_status_empty_string(
    client: AsyncClient,
    auth_headers: dict,
    project: Project,
    finding: Finding,
):
    resp = await _patch_status(
        client, auth_headers, str(project.id), str(finding.id), ""
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_status_missing_field(
    client: AsyncClient,
    auth_headers: dict,
    project: Project,
    finding: Finding,
):
    resp = await client.patch(
        f"/api/v1/projects/{project.id}/issues/{finding.id}",
        json={},
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ── Auth enforcement ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_status_unauthenticated(
    client: AsyncClient,
    project: Project,
    finding: Finding,
):
    resp = await _patch_status(client, {}, str(project.id), str(finding.id), "Resolved")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_status_invalid_token(
    client: AsyncClient,
    project: Project,
    finding: Finding,
):
    resp = await _patch_status(
        client,
        {"Authorization": "Bearer notavalidtoken"},
        str(project.id),
        str(finding.id),
        "Resolved",
    )
    assert resp.status_code == 401


# ── Not found ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_status_nonexistent_issue(
    client: AsyncClient,
    auth_headers: dict,
    project: Project,
):
    resp = await _patch_status(
        client, auth_headers, str(project.id), str(uuid.uuid4()), "Resolved"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_status_wrong_project(
    client: AsyncClient,
    auth_headers: dict,
    user: User,
    db: AsyncSession,
    project: Project,
    finding: Finding,
):
    """An issue that belongs to project A must return 404 when addressed via project B."""
    project_b = Project(
        id=uuid.uuid4(),
        name="Project B",
        default_branch="main",
        owner_id=user.id,
    )
    db.add(project_b)
    db.add(ProjectMembership(project_id=project_b.id, user_id=user.id, role="owner"))
    await db.flush()

    resp = await _patch_status(
        client, auth_headers, str(project_b.id), str(finding.id), "Resolved"
    )
    assert resp.status_code == 404


# ── Membership enforcement ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_status_no_membership(
    client: AsyncClient,
    project: Project,
    finding: Finding,
    second_user: User,
):
    """A user with no membership in the project must receive 403."""
    token = create_access_token(subject=str(second_user.id))
    resp = await _patch_status(
        client,
        {"Authorization": f"Bearer {token}"},
        str(project.id),
        str(finding.id),
        "Resolved",
    )
    assert resp.status_code == 403
