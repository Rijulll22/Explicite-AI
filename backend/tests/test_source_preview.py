"""
Tests for source code preview:
  - Unit tests for the source_reader service (path traversal, boundaries, missing files)
  - API integration tests (auth, project isolation, missing source, line highlighting)
"""
import os
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.analysis import AnalysisJob
from app.models.finding import Finding
from app.models.user import User
from app.models.project import Project
from app.services.source_reader import read_source_excerpt


# ── Unit tests for source_reader ──────────────────────────────────────────────

@pytest.fixture
def source_tree(tmp_path: Path):
    """Create a small fake source tree."""
    (tmp_path / "src").mkdir()
    lines = [f"line {i}" for i in range(1, 41)]   # 40 lines
    (tmp_path / "src" / "main.py").write_text("\n".join(lines), encoding="utf-8")
    return tmp_path


def test_read_excerpt_returns_correct_window(source_tree):
    excerpt = read_source_excerpt(source_tree, "src/main.py", target_line=20, context_lines=3)
    assert excerpt.available is True
    assert excerpt.target_line == 20
    numbers = [ln.number for ln in excerpt.lines]
    assert 17 <= numbers[0]
    assert numbers[-1] <= 23
    target_lines = [ln for ln in excerpt.lines if ln.is_target]
    assert len(target_lines) == 1
    assert target_lines[0].number == 20


def test_read_excerpt_line_1_start(source_tree):
    excerpt = read_source_excerpt(source_tree, "src/main.py", target_line=1, context_lines=5)
    assert excerpt.available is True
    assert excerpt.lines[0].number == 1


def test_read_excerpt_last_line(source_tree):
    excerpt = read_source_excerpt(source_tree, "src/main.py", target_line=40, context_lines=5)
    assert excerpt.available is True
    assert excerpt.lines[-1].number == 40


def test_read_excerpt_line_beyond_file(source_tree):
    excerpt = read_source_excerpt(source_tree, "src/main.py", target_line=9999, context_lines=5)
    assert excerpt.available is True
    assert excerpt.target_line is None   # line beyond EOF: no highlight


def test_read_excerpt_no_line_number(source_tree):
    excerpt = read_source_excerpt(source_tree, "src/main.py", target_line=None, context_lines=5)
    assert excerpt.available is True
    assert excerpt.target_line is None
    assert len(excerpt.lines) > 0


def test_read_excerpt_missing_file(source_tree):
    excerpt = read_source_excerpt(source_tree, "src/nonexistent.py", target_line=5)
    assert excerpt.available is False
    assert excerpt.message is not None


def test_read_excerpt_no_file_path(source_tree):
    excerpt = read_source_excerpt(source_tree, None, target_line=5)
    assert excerpt.available is False


def test_read_excerpt_path_traversal_blocked(source_tree):
    excerpt = read_source_excerpt(source_tree, "../../../etc/passwd", target_line=1)
    assert excerpt.available is False


def test_read_excerpt_absolute_path_blocked(source_tree):
    excerpt = read_source_excerpt(source_tree, "/etc/passwd", target_line=1)
    assert excerpt.available is False


def test_read_excerpt_dotdot_in_path_blocked(source_tree):
    excerpt = read_source_excerpt(source_tree, "src/../../other/secret.py", target_line=1)
    assert excerpt.available is False


def test_read_excerpt_symlink_blocked(tmp_path: Path):
    """A symlink anywhere in the resolved path is rejected."""
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    (real_dir / "target.py").write_text("secret", encoding="utf-8")
    link_dir = tmp_path / "src"
    try:
        link_dir.symlink_to(real_dir)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not supported on this platform/OS")
    excerpt = read_source_excerpt(tmp_path, "src/target.py", target_line=1)
    assert excerpt.available is False


def test_read_excerpt_windows_path_blocked(source_tree):
    excerpt = read_source_excerpt(source_tree, "C:\\Windows\\System32\\config\\SAM", target_line=1)
    assert excerpt.available is False


def test_read_excerpt_content_correct(source_tree):
    excerpt = read_source_excerpt(source_tree, "src/main.py", target_line=5, context_lines=2)
    assert excerpt.available is True
    lines_by_num = {ln.number: ln.content for ln in excerpt.lines}
    assert lines_by_num.get(5) == "line 5"


# ── API integration tests ─────────────────────────────────────────────────────

async def _make_job_with_source(
    db: AsyncSession,
    project: Project,
    source_dir: Path,
    file_name: str,
    file_content: str,
) -> tuple[AnalysisJob, Finding]:
    """Helper: write a real file and create a job+finding pointing at it."""
    (source_dir / file_name).write_text(file_content, encoding="utf-8")

    job = AnalysisJob(
        id=uuid.uuid4(),
        project_id=project.id,
        status="completed",
        source_path=str(source_dir),
        source_branch="main",
        bugs_count=1,
    )
    db.add(job)
    await db.flush()

    finding = Finding(
        id=uuid.uuid4(),
        analysis_job_id=job.id,
        project_id=project.id,
        engine_severity="High",
        risk_level="High",
        issue_type="Vulnerability",
        title="Test finding",
        rule_key="test:rule",
        file_path=file_name,
        line_number=3,
        status="Open",
    )
    db.add(finding)
    await db.flush()
    return job, finding


@pytest.mark.asyncio
async def test_source_endpoint_returns_excerpt(
    client: AsyncClient,
    db: AsyncSession,
    project: Project,
    user: User,
    auth_headers: dict,
    tmp_path: Path,
):
    source_dir = tmp_path / "src_test"
    source_dir.mkdir()
    content = "\n".join([f"code line {i}" for i in range(1, 21)])
    job, finding = await _make_job_with_source(db, project, source_dir, "app.py", content)
    await db.commit()

    resp = await client.get(
        f"/api/v1/projects/{project.id}/issues/{finding.id}/source",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["target_line"] == 3
    assert any(ln["is_target"] for ln in data["lines"])
    assert all("number" in ln and "content" in ln for ln in data["lines"])


@pytest.mark.asyncio
async def test_source_endpoint_unavailable_when_no_source_path(
    client: AsyncClient,
    db: AsyncSession,
    project: Project,
    finding: Finding,
    auth_headers: dict,
):
    """Fixtures: the conftest finding's analysis_job has no source_path → available=False."""
    resp = await client.get(
        f"/api/v1/projects/{project.id}/issues/{finding.id}/source",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["available"] is False


@pytest.mark.asyncio
async def test_source_endpoint_missing_file_returns_available_false(
    client: AsyncClient,
    db: AsyncSession,
    project: Project,
    user: User,
    auth_headers: dict,
    tmp_path: Path,
):
    source_dir = tmp_path / "empty_src"
    source_dir.mkdir()

    job = AnalysisJob(
        id=uuid.uuid4(),
        project_id=project.id,
        status="completed",
        source_path=str(source_dir),
        source_branch="main",
    )
    db.add(job)
    await db.flush()

    finding = Finding(
        id=uuid.uuid4(),
        analysis_job_id=job.id,
        project_id=project.id,
        engine_severity="High",
        risk_level="High",
        issue_type="Bug",
        title="Ghost finding",
        file_path="deleted.py",
        line_number=10,
        status="Open",
    )
    db.add(finding)
    await db.commit()

    resp = await client.get(
        f"/api/v1/projects/{project.id}/issues/{finding.id}/source",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert data["message"] is not None


@pytest.mark.asyncio
async def test_source_endpoint_requires_auth(client: AsyncClient, project: Project, finding: Finding):
    resp = await client.get(f"/api/v1/projects/{project.id}/issues/{finding.id}/source")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_source_endpoint_project_isolation(
    client: AsyncClient,
    db: AsyncSession,
    second_user: User,
    project: Project,
    finding: Finding,
):
    """second_user is not a member of project — must get 403/404."""
    token = create_access_token(subject=str(second_user.id))
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get(
        f"/api/v1/projects/{project.id}/issues/{finding.id}/source",
        headers=headers,
    )
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_source_endpoint_wrong_project_for_finding(
    client: AsyncClient,
    db: AsyncSession,
    user: User,
    auth_headers: dict,
    finding: Finding,
    tmp_path: Path,
):
    """Passing a different project_id that the user IS a member of must return 404."""
    other_project = Project(
        id=uuid.uuid4(),
        name="Other Project",
        default_branch="main",
        owner_id=user.id,
    )
    db.add(other_project)
    await db.flush()

    from app.models.project import ProjectMembership
    db.add(ProjectMembership(project_id=other_project.id, user_id=user.id, role="developer"))
    await db.commit()

    resp = await client.get(
        f"/api/v1/projects/{other_project.id}/issues/{finding.id}/source",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_source_nonexistent_issue(
    client: AsyncClient,
    project: Project,
    auth_headers: dict,
):
    fake_id = uuid.uuid4()
    resp = await client.get(
        f"/api/v1/projects/{project.id}/issues/{fake_id}/source",
        headers=auth_headers,
    )
    assert resp.status_code == 404
