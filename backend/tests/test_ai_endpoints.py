"""
Integration tests for AI endpoints.

POST /api/v1/projects/{project_id}/issues/{issue_id}/explain
POST /api/v1/projects/{project_id}/assistant

All tests stub the AI provider so no real model calls are made.
"""
import json
import uuid

import pytest

from app.services.ai_service import (
    AiInvalidResponseError,
    AiTimeoutError,
    AiUnavailableError,
    ExplainLevel,
    ExplainResult,
    FindingContext,
    NoneProvider,
)

_VALID_RESULT = ExplainResult(
    what="The analyzer detected eval() used with unsanitised input.",
    why="This allows arbitrary code execution.",
    how_it_arises="eval() is called without validation.",
    remediation="Replace eval() with ast.literal_eval() or another safe parser.",
    caveats="May be a false positive if inputs are sanitised upstream.",
    model_provider="anthropic",
    model_name="claude-haiku-4-5",
    grounded_in_finding=True,
    source_context_available=False,
)


class _SuccessProvider(NoneProvider):
    """Provider that always returns _VALID_RESULT for explain and a fixed chat reply."""

    async def explain(self, ctx: FindingContext, level: ExplainLevel) -> ExplainResult:
        return _VALID_RESULT

    async def chat(self, system: str, user_message: str) -> str:
        return "This is the AI assistant reply."


class _UnavailableProvider(NoneProvider):
    async def explain(self, ctx, level):
        raise AiUnavailableError("No model configured.")

    async def chat(self, system, user):
        raise AiUnavailableError("No model configured.")


class _TimeoutProvider(NoneProvider):
    async def explain(self, ctx, level):
        raise AiTimeoutError("Timed out.")

    async def chat(self, system, user):
        raise AiTimeoutError("Timed out.")


class _InvalidResponseProvider(NoneProvider):
    async def explain(self, ctx, level):
        raise AiInvalidResponseError("Model returned garbage.")

    async def chat(self, system, user):
        raise AiInvalidResponseError("Model returned garbage.")


def _patch_provider(monkeypatch, provider_instance):
    monkeypatch.setattr(
        "app.api.ai.get_provider",
        lambda: provider_instance,
    )


# ── /explain ──────────────────────────────────────────────────────────────────

class TestExplainEndpoint:
    def _url(self, project_id, issue_id):
        return f"/api/v1/projects/{project_id}/issues/{issue_id}/explain"

    @pytest.mark.asyncio
    async def test_requires_authentication(self, client, project, finding):
        resp = await client.post(self._url(project.id, finding.id), json={})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_rejects_non_member(
        self, client, second_user, project, finding, monkeypatch
    ):
        from app.core.security import create_access_token
        token = create_access_token(subject=str(second_user.id))
        _patch_provider(monkeypatch, _SuccessProvider())
        resp = await client.post(
            self._url(project.id, finding.id),
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_finding(
        self, client, auth_headers, project, monkeypatch
    ):
        _patch_provider(monkeypatch, _SuccessProvider())
        resp = await client.post(
            self._url(project.id, uuid.uuid4()),
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_when_finding_belongs_to_other_project(
        self, client, auth_headers, project, second_user, db, monkeypatch
    ):
        """Cross-project access: finding from another project must not be reachable."""
        from app.models.project import Project, ProjectMembership
        from app.models.finding import Finding
        from app.models.analysis import AnalysisJob

        other_project = Project(
            id=uuid.uuid4(), name="Other", default_branch="main", owner_id=second_user.id
        )
        db.add(other_project)
        db.add(ProjectMembership(
            project_id=other_project.id, user_id=second_user.id, role="owner"
        ))
        from datetime import datetime, timezone
        other_job = AnalysisJob(
            id=uuid.uuid4(),
            project_id=other_project.id,
            status="completed",
            source_branch="main",
            completed_at=datetime.now(tz=timezone.utc),
        )
        db.add(other_job)
        other_finding = Finding(
            id=uuid.uuid4(),
            analysis_job_id=other_job.id,
            project_id=other_project.id,
            engine_severity="High",
            risk_level="High",
            issue_type="Vulnerability",
            title="Cross-project finding",
            status="Open",
        )
        db.add(other_finding)
        await db.flush()

        _patch_provider(monkeypatch, _SuccessProvider())
        # Try to access other_finding via our project's URL — must 404
        resp = await client.post(
            self._url(project.id, other_finding.id),
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_503_when_model_unavailable(
        self, client, auth_headers, project, finding, monkeypatch
    ):
        _patch_provider(monkeypatch, _UnavailableProvider())
        resp = await client.post(
            self._url(project.id, finding.id),
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 503
        assert "No model" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_returns_503_on_timeout(
        self, client, auth_headers, project, finding, monkeypatch
    ):
        _patch_provider(monkeypatch, _TimeoutProvider())
        resp = await client.post(
            self._url(project.id, finding.id),
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_returns_502_on_invalid_response(
        self, client, auth_headers, project, finding, monkeypatch
    ):
        _patch_provider(monkeypatch, _InvalidResponseProvider())
        resp = await client.post(
            self._url(project.id, finding.id),
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 502

    @pytest.mark.asyncio
    async def test_successful_explanation_returns_all_fields(
        self, client, auth_headers, project, finding, monkeypatch
    ):
        _patch_provider(monkeypatch, _SuccessProvider())
        resp = await client.post(
            self._url(project.id, finding.id),
            json={"level": "intermediate"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["what"] != ""
        assert data["why"] != ""
        assert data["how_it_arises"] != ""
        assert data["remediation"] != ""
        assert data["caveats"] != ""
        assert data["grounded_in_finding"] is True
        assert data["cached"] is False
        assert str(finding.id) == data["finding_id"]

    @pytest.mark.asyncio
    async def test_caches_explanation_on_db(
        self, client, auth_headers, project, finding, db, monkeypatch
    ):
        _patch_provider(monkeypatch, _SuccessProvider())
        await client.post(
            self._url(project.id, finding.id),
            json={},
            headers=auth_headers,
        )
        await db.refresh(finding)
        assert finding.ai_explanation is not None
        assert "eval()" in finding.ai_explanation or "eval" in finding.ai_explanation

    @pytest.mark.asyncio
    async def test_returns_cached_explanation_without_calling_model(
        self, client, auth_headers, project, finding, db, monkeypatch
    ):
        # Pre-populate the cache
        finding.ai_explanation = (
            "WHAT: Cached what\n---\n"
            "WHY: Cached why\n---\n"
            "HOW IT ARISES: Cached how\n---\n"
            "REMEDIATION: Cached remediation\n---\n"
            "CAVEATS: Cached caveats"
        )
        db.add(finding)
        await db.flush()

        call_count = {"n": 0}

        class CountingProvider(_SuccessProvider):
            async def explain(self, ctx, level):
                call_count["n"] += 1
                return await super().explain(ctx, level)

        _patch_provider(monkeypatch, CountingProvider())
        resp = await client.post(
            self._url(project.id, finding.id),
            json={"force": False},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["cached"] is True
        assert call_count["n"] == 0

    @pytest.mark.asyncio
    async def test_force_regenerates_cached_explanation(
        self, client, auth_headers, project, finding, db, monkeypatch
    ):
        finding.ai_explanation = "WHAT: old\n---\nWHY: old\n---\nHOW IT ARISES: old\n---\nREMEDIATION: old\n---\nCAVEATS: old"
        db.add(finding)
        await db.flush()

        _patch_provider(monkeypatch, _SuccessProvider())
        resp = await client.post(
            self._url(project.id, finding.id),
            json={"force": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["cached"] is False

    @pytest.mark.asyncio
    async def test_invalid_level_returns_422(
        self, client, auth_headers, project, finding, monkeypatch
    ):
        _patch_provider(monkeypatch, _SuccessProvider())
        resp = await client.post(
            self._url(project.id, finding.id),
            json={"level": "expert"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_finding_not_modified_on_model_failure(
        self, client, auth_headers, project, finding, db, monkeypatch
    ):
        """FR-AI-07: finding.ai_explanation stays None on model failure."""
        _patch_provider(monkeypatch, _UnavailableProvider())
        await client.post(
            self._url(project.id, finding.id),
            json={},
            headers=auth_headers,
        )
        await db.refresh(finding)
        assert finding.ai_explanation is None


# ── /assistant ────────────────────────────────────────────────────────────────

class TestAssistantEndpoint:
    def _url(self, project_id):
        return f"/api/v1/projects/{project_id}/assistant"

    @pytest.mark.asyncio
    async def test_requires_authentication(self, client, project):
        resp = await client.post(self._url(project.id), json={"message": "help"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_rejects_non_member(self, client, second_user, project, monkeypatch):
        from app.core.security import create_access_token
        token = create_access_token(subject=str(second_user.id))
        _patch_provider(monkeypatch, _SuccessProvider())
        resp = await client.post(
            self._url(project.id),
            json={"message": "hello"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_returns_503_when_unavailable(
        self, client, auth_headers, project, monkeypatch
    ):
        _patch_provider(monkeypatch, _UnavailableProvider())
        resp = await client.post(
            self._url(project.id),
            json={"message": "What are my vulnerabilities?"},
            headers=auth_headers,
        )
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_successful_reply(
        self, client, auth_headers, project, monkeypatch
    ):
        _patch_provider(monkeypatch, _SuccessProvider())
        resp = await client.post(
            self._url(project.id),
            json={"message": "What are my vulnerabilities?"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reply"] != ""

    @pytest.mark.asyncio
    async def test_reply_with_issue_context(
        self, client, auth_headers, project, finding, monkeypatch
    ):
        _patch_provider(monkeypatch, _SuccessProvider())
        resp = await client.post(
            self._url(project.id),
            json={"message": "Explain this issue", "issue_id": str(finding.id)},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["grounded"] is True

    @pytest.mark.asyncio
    async def test_cross_project_issue_blocked(
        self, client, auth_headers, project, second_user, db, monkeypatch
    ):
        """A finding from another project cannot be used as context."""
        from app.models.project import Project, ProjectMembership
        from app.models.finding import Finding
        from app.models.analysis import AnalysisJob

        other_project = Project(
            id=uuid.uuid4(), name="Other", default_branch="main", owner_id=second_user.id
        )
        db.add(other_project)
        db.add(ProjectMembership(
            project_id=other_project.id, user_id=second_user.id, role="owner"
        ))
        from datetime import datetime, timezone
        other_job = AnalysisJob(
            id=uuid.uuid4(),
            project_id=other_project.id,
            status="completed",
            source_branch="main",
            completed_at=datetime.now(tz=timezone.utc),
        )
        db.add(other_job)
        other_finding = Finding(
            id=uuid.uuid4(),
            analysis_job_id=other_job.id,
            project_id=other_project.id,
            engine_severity="High",
            risk_level="High",
            issue_type="Bug",
            title="Other finding",
            status="Open",
        )
        db.add(other_finding)
        await db.flush()

        _patch_provider(monkeypatch, _SuccessProvider())
        resp = await client.post(
            self._url(project.id),
            json={"message": "help", "issue_id": str(other_finding.id)},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_empty_message_rejected(
        self, client, auth_headers, project, monkeypatch
    ):
        _patch_provider(monkeypatch, _SuccessProvider())
        resp = await client.post(
            self._url(project.id),
            json={"message": "   "},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_oversized_message_rejected(
        self, client, auth_headers, project, monkeypatch
    ):
        _patch_provider(monkeypatch, _SuccessProvider())
        resp = await client.post(
            self._url(project.id),
            json={"message": "x" * 1001},
            headers=auth_headers,
        )
        assert resp.status_code == 422
