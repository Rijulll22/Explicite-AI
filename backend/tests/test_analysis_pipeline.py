"""
End-to-end tests for the code analysis pipeline.

Tests cover:
- Valid ZIP upload → 202 + queued job
- Job completes and findings are stored (background task integration)
- Empty ZIP, malformed ZIP, non-zip bytes → 422
- Path traversal detected in ZIP entries → 422
- Empty upload body → 400
- Unauthenticated access → 401
- Missing project membership → 403
- Viewer cannot submit (min_role = developer) → 403
- Job status list + get endpoints
- Finding isolation: project A's job not accessible from project B
- Semgrep smoke test (marked slow): known-vulnerable fixture produces ≥ 1 finding

Architecture note:
Background tasks need committed DB data, but the shared `client` fixture in
conftest uses a test session that never commits.  A local `committing_client`
fixture uses the real get_db (which commits) so background tasks can see data.
The autouse `truncate_tables` fixture from conftest still cleans up between tests.
"""
import asyncio
import io
import uuid

from app.services.job_runner import _sanitize_failure_reason
import zipfile

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.core.security import create_access_token, hash_password
from app.database import init_db
from app.main import app
from app.models.project import Project, ProjectMembership
from app.models.user import User

_TEST_DB_URL = settings.TEST_DATABASE_URL or settings.DATABASE_URL.replace(
    "/explicite_ai", "/test_explicite_ai"
)

# ── ZIP helpers ───────────────────────────────────────────────────────────────

# Python with a SQL injection pattern — r/python semgrep rules should flag it.
_VULN_PYTHON = b"""
import sqlite3

def get_user(db_path, username):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    cursor.execute(query)
    return cursor.fetchall()
"""

_SAFE_PYTHON = b"""
def add(a, b):
    return a + b
"""


def _make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _zip_with_traversal() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        info = zipfile.ZipInfo("../../evil.py")
        zf.writestr(info, b"print('pwned')")
    return buf.getvalue()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _wait_terminal(
    client, project_id: str, job_id: str, token: str, *, timeout: int = 120
) -> dict:
    """Poll job status until completed or failed, return the body."""
    for _ in range(timeout * 5):
        await asyncio.sleep(0.2)
        r = await client.get(
            f"/api/v1/projects/{project_id}/analyse/{job_id}",
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        if data["status"] in ("completed", "failed"):
            return data
    pytest.fail(f"Job {job_id} did not reach terminal state within {timeout}s")


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def committing_client(setup_test_db):
    """
    HTTP test client that uses the *real* get_db dependency (commits after
    each request).  Background tasks can therefore see committed data.
    truncate_tables (autouse from conftest) cleans up after each test.
    """
    init_db(_TEST_DB_URL)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as c:
        yield c


@pytest_asyncio.fixture
async def owner(setup_test_db):
    """Insert a user and return (User, token) — uses the real test DB."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    engine = create_async_engine(_TEST_DB_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        u = User(
            id=uuid.uuid4(),
            email="pipeline_owner@test.invalid",
            password_hash=hash_password("TestPass1!"),
            full_name="Pipeline Owner",
            system_role="member",
            is_email_verified=True,
            is_active=True,
        )
        session.add(u)
        await session.commit()
        token = create_access_token(subject=str(u.id))
    await engine.dispose()
    return u, token


@pytest_asyncio.fixture
async def intruder_token(setup_test_db):
    """A user with no project memberships."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    engine = create_async_engine(_TEST_DB_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        u = User(
            id=uuid.uuid4(),
            email="pipeline_intruder@test.invalid",
            password_hash=hash_password("TestPass1!"),
            full_name="Intruder",
            system_role="member",
            is_email_verified=True,
            is_active=True,
        )
        session.add(u)
        await session.commit()
        token = create_access_token(subject=str(u.id))
    await engine.dispose()
    return token


@pytest_asyncio.fixture
async def test_project(committing_client, owner):
    """Create a project via API for the owner user."""
    user_obj, token = owner
    r = await committing_client.post(
        "/api/v1/projects",
        json={"name": "PipelineProject", "description": "test"},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest_asyncio.fixture
async def viewer_token(setup_test_db, test_project):
    """Create a viewer user and add them to test_project directly via DB."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(_TEST_DB_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        u = User(
            id=uuid.uuid4(),
            email="pipeline_viewer@test.invalid",
            password_hash=hash_password("TestPass1!"),
            full_name="Viewer",
            system_role="member",
            is_email_verified=True,
            is_active=True,
        )
        session.add(u)
        await session.flush()
        membership = ProjectMembership(
            project_id=uuid.UUID(test_project),
            user_id=u.id,
            role="viewer",
        )
        session.add(membership)
        await session.commit()
        token = create_access_token(subject=str(u.id))
    await engine.dispose()
    return token


# ── Failure reason sanitization (unit tests) ──────────────────────────────────

class TestSanitizeFailureReason:
    def test_strips_source_path(self):
        msg = "Semgrep returned error: /app/uploads/abc-123/def-456 is invalid"
        result = _sanitize_failure_reason(msg, "/app/uploads/abc-123/def-456")
        assert "/app/uploads" not in result
        assert "<source_dir>" in result

    def test_strips_windows_path(self):
        msg = r"Semgrep returned error: C:\uploads\proj\job some error"
        result = _sanitize_failure_reason(msg, r"C:\uploads\proj\job")
        assert "uploads" not in result
        assert "<source_dir>" in result

    def test_no_source_path_is_noop(self):
        msg = "Semgrep timed out after 300s"
        assert _sanitize_failure_reason(msg, None) == msg

    def test_truncates_to_500(self):
        msg = "x" * 600
        assert len(_sanitize_failure_reason(msg, None)) == 500

    def test_safe_messages_unchanged(self):
        for msg in [
            "Semgrep timed out after 300s",
            "Semgrep executable not found at runtime",
            "Semgrep not found. Install it with: pip install semgrep",
            "Unexpected error during analysis",
        ]:
            result = _sanitize_failure_reason(msg, "/some/secret/path")
            assert msg == result  # no path present, message unchanged


# ── Submit analysis ───────────────────────────────────────────────────────────

class TestSubmitAnalysis:
    async def test_valid_zip_returns_202_queued(
        self, committing_client, owner, test_project
    ):
        _, token = owner
        data = _make_zip({"main.py": _SAFE_PYTHON})
        r = await committing_client.post(
            f"/api/v1/projects/{test_project}/analyse",
            headers=_auth(token),
            files={"source": ("project.zip", data, "application/zip")},
        )
        assert r.status_code == 202, r.text
        body = r.json()
        assert body["status"] == "queued"
        assert body["project_id"] == test_project
        assert body["id"] is not None

    async def test_job_completes_for_safe_code(
        self, committing_client, owner, test_project
    ):
        _, token = owner
        data = _make_zip({"main.py": _SAFE_PYTHON})
        r = await committing_client.post(
            f"/api/v1/projects/{test_project}/analyse",
            headers=_auth(token),
            files={"source": ("project.zip", data, "application/zip")},
        )
        assert r.status_code == 202
        job_id = r.json()["id"]

        final = await _wait_terminal(committing_client, test_project, job_id, token)
        assert final["status"] == "completed"
        assert final["findings_count"] is not None

    async def test_empty_zip_returns_422(
        self, committing_client, owner, test_project
    ):
        _, token = owner
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w"):
            pass
        r = await committing_client.post(
            f"/api/v1/projects/{test_project}/analyse",
            headers=_auth(token),
            files={"source": ("empty.zip", buf.getvalue(), "application/zip")},
        )
        assert r.status_code == 422
        assert "empty" in r.json()["detail"].lower()

    async def test_malformed_zip_returns_422(
        self, committing_client, owner, test_project
    ):
        _, token = owner
        r = await committing_client.post(
            f"/api/v1/projects/{test_project}/analyse",
            headers=_auth(token),
            files={"source": ("bad.zip", b"not a zip file at all", "application/zip")},
        )
        assert r.status_code == 422

    async def test_path_traversal_returns_422(
        self, committing_client, owner, test_project
    ):
        _, token = owner
        r = await committing_client.post(
            f"/api/v1/projects/{test_project}/analyse",
            headers=_auth(token),
            files={"source": ("traversal.zip", _zip_with_traversal(), "application/zip")},
        )
        assert r.status_code == 422
        assert "traversal" in r.json()["detail"].lower()

    async def test_unauthenticated_returns_401(
        self, committing_client, test_project
    ):
        data = _make_zip({"main.py": _SAFE_PYTHON})
        r = await committing_client.post(
            f"/api/v1/projects/{test_project}/analyse",
            files={"source": ("project.zip", data, "application/zip")},
        )
        assert r.status_code == 401

    async def test_no_membership_returns_403(
        self, committing_client, intruder_token, test_project
    ):
        data = _make_zip({"main.py": _SAFE_PYTHON})
        r = await committing_client.post(
            f"/api/v1/projects/{test_project}/analyse",
            headers=_auth(intruder_token),
            files={"source": ("project.zip", data, "application/zip")},
        )
        assert r.status_code == 403

    async def test_viewer_cannot_submit(
        self, committing_client, viewer_token, test_project
    ):
        data = _make_zip({"main.py": _SAFE_PYTHON})
        r = await committing_client.post(
            f"/api/v1/projects/{test_project}/analyse",
            headers=_auth(viewer_token),
            files={"source": ("project.zip", data, "application/zip")},
        )
        assert r.status_code == 403

    async def test_empty_file_body_returns_400(
        self, committing_client, owner, test_project
    ):
        _, token = owner
        r = await committing_client.post(
            f"/api/v1/projects/{test_project}/analyse",
            headers=_auth(token),
            files={"source": ("empty.zip", b"", "application/zip")},
        )
        assert r.status_code == 400


# ── Job status endpoints ──────────────────────────────────────────────────────

class TestJobStatus:
    async def test_list_jobs_empty(self, committing_client, owner, test_project):
        _, token = owner
        r = await committing_client.get(
            f"/api/v1/projects/{test_project}/analyse",
            headers=_auth(token),
        )
        assert r.status_code == 200
        assert r.json() == []

    async def test_list_contains_submitted_job(
        self, committing_client, owner, test_project
    ):
        _, token = owner
        data = _make_zip({"main.py": _SAFE_PYTHON})
        sub = await committing_client.post(
            f"/api/v1/projects/{test_project}/analyse",
            headers=_auth(token),
            files={"source": ("project.zip", data, "application/zip")},
        )
        job_id = sub.json()["id"]

        r = await committing_client.get(
            f"/api/v1/projects/{test_project}/analyse",
            headers=_auth(token),
        )
        assert r.status_code == 200
        assert job_id in [j["id"] for j in r.json()]

    async def test_get_job_not_found_returns_404(
        self, committing_client, owner, test_project
    ):
        _, token = owner
        r = await committing_client.get(
            f"/api/v1/projects/{test_project}/analyse/00000000-0000-0000-0000-000000000000",
            headers=_auth(token),
        )
        assert r.status_code == 404

    async def test_job_from_other_project_returns_404(
        self, committing_client, owner, test_project
    ):
        _, token = owner
        r2 = await committing_client.post(
            "/api/v1/projects",
            json={"name": "OtherProject"},
            headers=_auth(token),
        )
        other_pid = r2.json()["id"]

        data = _make_zip({"main.py": _SAFE_PYTHON})
        sub = await committing_client.post(
            f"/api/v1/projects/{other_pid}/analyse",
            headers=_auth(token),
            files={"source": ("project.zip", data, "application/zip")},
        )
        job_id = sub.json()["id"]

        r = await committing_client.get(
            f"/api/v1/projects/{test_project}/analyse/{job_id}",
            headers=_auth(token),
        )
        assert r.status_code == 404

    async def test_unauthenticated_list_returns_401(
        self, committing_client, test_project
    ):
        r = await committing_client.get(
            f"/api/v1/projects/{test_project}/analyse"
        )
        assert r.status_code == 401

    async def test_no_membership_list_returns_403(
        self, committing_client, intruder_token, test_project
    ):
        r = await committing_client.get(
            f"/api/v1/projects/{test_project}/analyse",
            headers=_auth(intruder_token),
        )
        assert r.status_code == 403


# ── Finding isolation ─────────────────────────────────────────────────────────

class TestFindingIsolation:
    async def test_findings_not_visible_across_projects(
        self, committing_client, owner
    ):
        _, token = owner
        rA = await committing_client.post(
            "/api/v1/projects",
            json={"name": "IsoA"},
            headers=_auth(token),
        )
        rB = await committing_client.post(
            "/api/v1/projects",
            json={"name": "IsoB"},
            headers=_auth(token),
        )
        pid_a, pid_b = rA.json()["id"], rB.json()["id"]

        data = _make_zip({"main.py": _SAFE_PYTHON})
        sub = await committing_client.post(
            f"/api/v1/projects/{pid_a}/analyse",
            headers=_auth(token),
            files={"source": ("project.zip", data, "application/zip")},
        )
        job_id = sub.json()["id"]
        await _wait_terminal(committing_client, pid_a, job_id, token)

        r = await committing_client.get(
            f"/api/v1/projects/{pid_b}/issues",
            headers=_auth(token),
        )
        assert r.status_code == 200
        assert r.json()["total"] == 0


# ── Semgrep smoke test (slow) ─────────────────────────────────────────────────

@pytest.mark.slow
class TestSemgrepSmoke:
    """
    Submit a known-vulnerable Python file and assert semgrep produces ≥ 1 finding.
    Requires internet access on first run (r/python rules are cached locally after).
    """

    async def test_vulnerable_code_produces_findings(
        self, committing_client, owner
    ):
        _, token = owner
        r = await committing_client.post(
            "/api/v1/projects",
            json={"name": "SmokeTest"},
            headers=_auth(token),
        )
        pid = r.json()["id"]

        data = _make_zip({"app.py": _VULN_PYTHON})
        sub = await committing_client.post(
            f"/api/v1/projects/{pid}/analyse",
            headers=_auth(token),
            files={"source": ("project.zip", data, "application/zip")},
        )
        assert sub.status_code == 202
        job_id = sub.json()["id"]

        final = await _wait_terminal(
            committing_client, pid, job_id, token, timeout=180
        )
        assert final["status"] == "completed", (
            f"Job failed: {final.get('failure_reason')}"
        )
        assert final["findings_count"] is not None

        issues_r = await committing_client.get(
            f"/api/v1/projects/{pid}/issues",
            headers=_auth(token),
        )
        assert issues_r.status_code == 200
        issues = issues_r.json()
        assert issues["total"] > 0, (
            "Expected ≥ 1 finding for the SQL injection fixture"
        )
        for issue in issues["items"]:
            assert issue["status"] in ("Open", "In Review", "Resolved")
