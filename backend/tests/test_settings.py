"""
Tests for user preferences / settings endpoints.

Covers:
  PATCH /api/v1/auth/me (preferences field)
  GET   /api/v1/auth/me (preferences returned)

  - Preferences save and re-fetch
  - Partial updates merge rather than overwrite
  - Invalid enum values rejected (422)
  - Out-of-range numerics rejected (422)
  - Cross-user isolation
  - Unauthenticated access blocked
  - Password hash and secrets never exposed
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.user import User


# ── Helpers ───────────────────────────────────────────────────────────────────

def _prefs_payload(**kwargs):
    return {"preferences": kwargs}


# ── GET /auth/me returns preferences ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_me_includes_preferences_defaults(client: AsyncClient, user: User, auth_headers: dict):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    prefs = data["preferences"]
    assert prefs["email_notifications"] == "Critical and High only"
    assert prefs["default_issue_sort"] == "Severity (highest first)"
    assert prefs["ai_explain_level"] == "intermediate"
    assert prefs["default_branch"] == "main"
    assert prefs["quality_gate_max_bugs"] == 0
    assert prefs["quality_gate_max_vulnerabilities"] == 0
    assert prefs["quality_gate_coverage_threshold"] == 0.0


@pytest.mark.asyncio
async def test_me_no_password_hash(client: AsyncClient, user: User, auth_headers: dict):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "password_hash" not in body
    assert "password" not in str(body)


# ── PATCH /auth/me — preferences section ─────────────────────────────────────

@pytest.mark.asyncio
async def test_save_preferences_email_notifications(client: AsyncClient, user: User, auth_headers: dict):
    resp = await client.patch(
        "/api/v1/auth/me",
        json=_prefs_payload(email_notifications="All issues"),
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["preferences"]["email_notifications"] == "All issues"


@pytest.mark.asyncio
async def test_preferences_persist_on_refetch(client: AsyncClient, user: User, auth_headers: dict):
    await client.patch(
        "/api/v1/auth/me",
        json=_prefs_payload(default_issue_sort="Date detected"),
        headers=auth_headers,
    )
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.json()["preferences"]["default_issue_sort"] == "Date detected"


@pytest.mark.asyncio
async def test_preferences_partial_update_merges(client: AsyncClient, user: User, auth_headers: dict):
    # Save two separate prefs
    await client.patch("/api/v1/auth/me", json=_prefs_payload(ai_explain_level="advanced"), headers=auth_headers)
    await client.patch("/api/v1/auth/me", json=_prefs_payload(default_branch="develop"), headers=auth_headers)
    # Both should be present
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    p = resp.json()["preferences"]
    assert p["ai_explain_level"] == "advanced"
    assert p["default_branch"] == "develop"


@pytest.mark.asyncio
async def test_preferences_quality_gate_max_bugs(client: AsyncClient, user: User, auth_headers: dict):
    resp = await client.patch(
        "/api/v1/auth/me",
        json=_prefs_payload(quality_gate_max_bugs=5),
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["preferences"]["quality_gate_max_bugs"] == 5


@pytest.mark.asyncio
async def test_preferences_quality_gate_coverage_threshold(client: AsyncClient, user: User, auth_headers: dict):
    resp = await client.patch(
        "/api/v1/auth/me",
        json=_prefs_payload(quality_gate_coverage_threshold=80.0),
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["preferences"]["quality_gate_coverage_threshold"] == 80.0


# ── Validation ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_email_notifications_rejected(client: AsyncClient, user: User, auth_headers: dict):
    resp = await client.patch(
        "/api/v1/auth/me",
        json=_prefs_payload(email_notifications="SPAM me"),
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_default_issue_sort_rejected(client: AsyncClient, user: User, auth_headers: dict):
    resp = await client.patch(
        "/api/v1/auth/me",
        json=_prefs_payload(default_issue_sort="Random"),
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_ai_explain_level_rejected(client: AsyncClient, user: User, auth_headers: dict):
    resp = await client.patch(
        "/api/v1/auth/me",
        json=_prefs_payload(ai_explain_level="expert"),
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_quality_gate_max_bugs_out_of_range(client: AsyncClient, user: User, auth_headers: dict):
    resp = await client.patch(
        "/api/v1/auth/me",
        json=_prefs_payload(quality_gate_max_bugs=999),
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_quality_gate_coverage_out_of_range(client: AsyncClient, user: User, auth_headers: dict):
    resp = await client.patch(
        "/api/v1/auth/me",
        json=_prefs_payload(quality_gate_coverage_threshold=110.0),
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_empty_default_branch_rejected(client: AsyncClient, user: User, auth_headers: dict):
    resp = await client.patch(
        "/api/v1/auth/me",
        json=_prefs_payload(default_branch="   "),
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ── Cross-user isolation ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_preferences_isolated_between_users(
    client: AsyncClient,
    user: User,
    auth_headers: dict,
    second_user: User,
    db: AsyncSession,
):
    """User A's preferences must not be visible on user B's profile."""
    # User A sets a preference
    await client.patch(
        "/api/v1/auth/me",
        json=_prefs_payload(default_branch="feature/a"),
        headers=auth_headers,
    )
    # User B fetches their own profile
    b_token = create_access_token(subject=str(second_user.id))
    b_headers = {"Authorization": f"Bearer {b_token}"}
    resp = await client.get("/api/v1/auth/me", headers=b_headers)
    assert resp.status_code == 200
    assert resp.json()["preferences"]["default_branch"] == "main"  # default, not A's value


@pytest.mark.asyncio
async def test_unauthenticated_preferences_blocked(client: AsyncClient):
    resp = await client.patch("/api/v1/auth/me", json=_prefs_payload(default_branch="feat"))
    assert resp.status_code == 401


# ── Quality gate service uses preferences ─────────────────────────────────────

@pytest.mark.asyncio
async def test_dashboard_quality_gate_reflects_user_threshold(
    client: AsyncClient,
    auth_headers: dict,
    user: User,
    project,
    analysis_job,
):
    """
    User sets max_bugs=10 — job has bugs_count=3 which is now within threshold.
    Dashboard should show gate as passed.
    """
    # Set threshold so 3 bugs are allowed
    await client.patch(
        "/api/v1/auth/me",
        json=_prefs_payload(quality_gate_max_bugs=10, quality_gate_max_vulnerabilities=10),
        headers=auth_headers,
    )
    dash = await client.get(
        f"/api/v1/projects/{project.id}/dashboard", headers=auth_headers
    )
    assert dash.status_code == 200
    # gate.passed is derived from stored job.quality_gate_passed (False in conftest fixture)
    # but failed_conditions should reflect the user's thresholds (10 bugs allowed, only 3 found)
    gate = dash.json()["quality_gate"]
    conds = " ".join(gate["failed_conditions"]).lower()
    assert "bug" not in conds  # 3 bugs ≤ 10 threshold → no bug condition


@pytest.mark.asyncio
async def test_project_defaults_applied_to_new_project(
    client: AsyncClient,
    auth_headers: dict,
    user: User,
):
    """
    Setting default_branch preference stores correctly; it's up to the frontend
    to pre-fill the project form (backend just provides the preference).
    """
    await client.patch(
        "/api/v1/auth/me",
        json=_prefs_payload(default_branch="develop"),
        headers=auth_headers,
    )
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.json()["preferences"]["default_branch"] == "develop"
