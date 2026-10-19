"""Integration tests for suggested-fix endpoints."""
import uuid
from datetime import datetime, timezone

import pytest

from app.models.analysis import AnalysisJob
from app.models.finding import Finding
from app.models.project import Project, ProjectMembership
from app.models.suggested_fix import SuggestedFix
from app.services.ai_service import (
    AiUnavailableError,
    FixContext,
    FixResult,
    NoneProvider,
)


# ── Test provider helpers ─────────────────────────────────────────────────────

class _SuccessProvider(NoneProvider):
    """Provider that returns a canned valid fix result."""
    async def generate_fix(self, ctx: FixContext) -> FixResult:
        return FixResult(
            proposed_lines=[
                'PreparedStatement stmt = conn.prepareStatement(',
                '    "SELECT * FROM students WHERE id=?");',
                'stmt.setString(1, userId);',
            ],
            rationale="Use a parameterised query to prevent SQL injection.",
            caveats="Ensure the Connection object is available in scope.",
            model_provider="anthropic",
            model_name="claude-haiku-4-5",
        )


def _patch_provider(monkeypatch, provider_instance):
    monkeypatch.setattr("app.api.fixes.get_provider", lambda: provider_instance)


# ── Generate fix ──────────────────────────────────────────────────────────────

class TestGenerateFix:
    @pytest.mark.asyncio
    async def test_returns_201(self, client, auth_headers, finding, monkeypatch):
        _patch_provider(monkeypatch, _SuccessProvider())
        resp = await client.post(
            f"/api/v1/projects/{finding.project_id}/issues/{finding.id}/fix",
            headers=auth_headers,
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_response_fields(self, client, auth_headers, finding, monkeypatch):
        _patch_provider(monkeypatch, _SuccessProvider())
        resp = await client.post(
            f"/api/v1/projects/{finding.project_id}/issues/{finding.id}/fix",
            headers=auth_headers,
        )
        data = resp.json()
        assert data["status"] == "proposed"
        assert data["finding_id"] == str(finding.id)
        assert data["model_provider"] == "anthropic"
        assert data["rationale"] is not None

    @pytest.mark.asyncio
    async def test_returns_503_when_no_provider(self, client, auth_headers, finding, monkeypatch):
        _patch_provider(monkeypatch, NoneProvider())
        resp = await client.post(
            f"/api/v1/projects/{finding.project_id}/issues/{finding.id}/fix",
            headers=auth_headers,
        )
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_requires_auth(self, client, finding):
        resp = await client.post(
            f"/api/v1/projects/{finding.project_id}/issues/{finding.id}/fix"
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_404_for_wrong_project(
        self, client, auth_headers, finding, monkeypatch
    ):
        _patch_provider(monkeypatch, _SuccessProvider())
        wrong_project_id = uuid.uuid4()
        resp = await client.post(
            f"/api/v1/projects/{wrong_project_id}/issues/{finding.id}/fix",
            headers=auth_headers,
        )
        # Either 403 (not a member) or 404 (finding not in project)
        assert resp.status_code in (403, 404)

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_issue(
        self, client, auth_headers, project, monkeypatch
    ):
        _patch_provider(monkeypatch, _SuccessProvider())
        resp = await client.post(
            f"/api/v1/projects/{project.id}/issues/{uuid.uuid4()}/fix",
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ── Get fix detail ────────────────────────────────────────────────────────────

class TestGetFix:
    @pytest.fixture
    async def proposed_fix(self, db, finding):
        fix = SuggestedFix(
            id=uuid.uuid4(),
            finding_id=finding.id,
            project_id=finding.project_id,
            analysis_job_id=finding.analysis_job_id,
            target_file="StudentDAO.java",
            original_hash="a" * 64,
            original_snippet="original code",
            proposed_snippet="fixed code",
            unified_diff="--- a/StudentDAO.java\n+++ b/StudentDAO.java\n",
            snippet_start_line=40,
            snippet_end_line=44,
            rationale="Parameterise the query.",
            caveats="Test thoroughly.",
            status="proposed",
            source_available=True,
            model_provider="anthropic",
            model_name="claude-haiku-4-5",
        )
        db.add(fix)
        await db.flush()
        return fix

    @pytest.mark.asyncio
    async def test_returns_200(self, client, auth_headers, proposed_fix, finding):
        resp = await client.get(
            f"/api/v1/projects/{finding.project_id}/fixes/{proposed_fix.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_unified_diff(self, client, auth_headers, proposed_fix, finding):
        resp = await client.get(
            f"/api/v1/projects/{finding.project_id}/fixes/{proposed_fix.id}",
            headers=auth_headers,
        )
        data = resp.json()
        assert "StudentDAO.java" in (data["unified_diff"] or "")

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_fix(self, client, auth_headers, project):
        resp = await client.get(
            f"/api/v1/projects/{project.id}/fixes/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_requires_auth(self, client, proposed_fix, finding):
        resp = await client.get(
            f"/api/v1/projects/{finding.project_id}/fixes/{proposed_fix.id}"
        )
        assert resp.status_code == 401


# ── List fixes ────────────────────────────────────────────────────────────────

class TestListFixes:
    @pytest.mark.asyncio
    async def test_returns_list(self, client, auth_headers, finding, monkeypatch):
        _patch_provider(monkeypatch, _SuccessProvider())
        # Generate a fix first
        await client.post(
            f"/api/v1/projects/{finding.project_id}/issues/{finding.id}/fix",
            headers=auth_headers,
        )
        resp = await client.get(
            f"/api/v1/projects/{finding.project_id}/issues/{finding.id}/fixes",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_empty_list_when_no_fixes(self, client, auth_headers, finding):
        resp = await client.get(
            f"/api/v1/projects/{finding.project_id}/issues/{finding.id}/fixes",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ── Approve fix ───────────────────────────────────────────────────────────────

class TestApproveFix:
    @pytest.fixture
    async def proposed_fix(self, db, finding):
        fix = SuggestedFix(
            id=uuid.uuid4(),
            finding_id=finding.id,
            project_id=finding.project_id,
            analysis_job_id=finding.analysis_job_id,
            target_file="StudentDAO.java",
            original_hash="a" * 64,
            original_snippet="original",
            proposed_snippet="proposed",
            unified_diff="diff",
            status="proposed",
            source_available=True,
            model_provider="anthropic",
            model_name="claude-haiku-4-5",
        )
        db.add(fix)
        await db.flush()
        return fix

    @pytest.mark.asyncio
    async def test_approve_transitions_to_approved(
        self, client, auth_headers, proposed_fix, finding
    ):
        resp = await client.post(
            f"/api/v1/projects/{finding.project_id}/fixes/{proposed_fix.id}/approve",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
        assert resp.json()["approved_at"] is not None

    @pytest.mark.asyncio
    async def test_cannot_approve_already_approved(
        self, client, auth_headers, proposed_fix, finding
    ):
        # Approve once
        await client.post(
            f"/api/v1/projects/{finding.project_id}/fixes/{proposed_fix.id}/approve",
            headers=auth_headers,
        )
        # Approve again
        resp = await client.post(
            f"/api/v1/projects/{finding.project_id}/fixes/{proposed_fix.id}/approve",
            headers=auth_headers,
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_requires_developer_role(
        self, client, second_user, finding, proposed_fix, db
    ):
        from app.core.security import create_access_token
        # second_user has no membership — should get 403
        token = create_access_token(subject=str(second_user.id))
        resp = await client.post(
            f"/api/v1/projects/{finding.project_id}/fixes/{proposed_fix.id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


# ── Reject fix ────────────────────────────────────────────────────────────────

class TestRejectFix:
    @pytest.fixture
    async def proposed_fix(self, db, finding):
        fix = SuggestedFix(
            id=uuid.uuid4(),
            finding_id=finding.id,
            project_id=finding.project_id,
            analysis_job_id=finding.analysis_job_id,
            status="proposed",
            source_available=False,
            model_provider="anthropic",
            model_name="claude-haiku-4-5",
        )
        db.add(fix)
        await db.flush()
        return fix

    @pytest.mark.asyncio
    async def test_reject_transitions_to_rejected(
        self, client, auth_headers, proposed_fix, finding
    ):
        resp = await client.post(
            f"/api/v1/projects/{finding.project_id}/fixes/{proposed_fix.id}/reject",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"
        assert resp.json()["rejected_at"] is not None

    @pytest.mark.asyncio
    async def test_cannot_reject_already_rejected(
        self, client, auth_headers, proposed_fix, finding
    ):
        await client.post(
            f"/api/v1/projects/{finding.project_id}/fixes/{proposed_fix.id}/reject",
            headers=auth_headers,
        )
        resp = await client.post(
            f"/api/v1/projects/{finding.project_id}/fixes/{proposed_fix.id}/reject",
            headers=auth_headers,
        )
        assert resp.status_code == 409


# ── Download ZIP ──────────────────────────────────────────────────────────────

class TestDownloadZip:
    @pytest.mark.asyncio
    async def test_returns_409_for_proposed_fix(
        self, client, auth_headers, db, finding
    ):
        fix = SuggestedFix(
            id=uuid.uuid4(),
            finding_id=finding.id,
            project_id=finding.project_id,
            analysis_job_id=finding.analysis_job_id,
            status="proposed",
            source_available=True,
            model_provider="anthropic",
            model_name="claude-haiku-4-5",
        )
        db.add(fix)
        await db.flush()

        resp = await client.get(
            f"/api/v1/projects/{finding.project_id}/fixes/{fix.id}/download",
            headers=auth_headers,
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_returns_409_when_source_not_available(
        self, client, auth_headers, db, finding
    ):
        fix = SuggestedFix(
            id=uuid.uuid4(),
            finding_id=finding.id,
            project_id=finding.project_id,
            analysis_job_id=finding.analysis_job_id,
            status="approved",
            source_available=False,   # no source
            model_provider="anthropic",
            model_name="claude-haiku-4-5",
        )
        db.add(fix)
        await db.flush()

        resp = await client.get(
            f"/api/v1/projects/{finding.project_id}/fixes/{fix.id}/download",
            headers=auth_headers,
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_returns_zip_bytes(
        self, client, auth_headers, db, finding, analysis_job, tmp_path, monkeypatch
    ):
        """Approved fix with real source — download should return a ZIP."""
        import hashlib
        import zipfile
        import io

        # Set up a fake source directory with the target file
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        java_file = src_dir / "StudentDAO.java"
        original = 'String q = "SELECT * FROM students WHERE id=" + userId;\n'
        original_bytes = original.encode("utf-8")
        java_file.write_bytes(original_bytes)   # binary write: no \r\n conversion
        file_hash = hashlib.sha256(original_bytes).hexdigest()

        # Point the analysis job at this source dir
        analysis_job.source_path = str(src_dir)
        db.add(analysis_job)
        await db.flush()

        fix = SuggestedFix(
            id=uuid.uuid4(),
            finding_id=finding.id,
            project_id=finding.project_id,
            analysis_job_id=analysis_job.id,
            target_file="StudentDAO.java",
            original_hash=file_hash,
            original_snippet=original,
            proposed_snippet="PreparedStatement stmt = conn.prepareStatement(\"SELECT * FROM students WHERE id=?\");\n",
            status="approved",
            source_available=True,
            model_provider="anthropic",
            model_name="claude-haiku-4-5",
        )
        db.add(fix)
        await db.flush()

        resp = await client.get(
            f"/api/v1/projects/{finding.project_id}/fixes/{fix.id}/download",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        assert "StudentDAO.java" in zf.namelist()
        patched = zf.read("StudentDAO.java").decode()
        assert "PreparedStatement" in patched
