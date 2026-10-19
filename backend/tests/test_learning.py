"""
Tests for learning and profile-update endpoints:

  GET  /api/v1/learning/resources
  GET  /api/v1/learning/paths
  GET  /api/v1/learning/progress
  PATCH /api/v1/auth/me
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.learning import LearningPath, LearningPathResource, LearningResource, UserLearningProgress
from app.models.user import User


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def resource_sql(db: AsyncSession, user: User) -> LearningResource:
    r = LearningResource(
        id=uuid.uuid4(),
        title="Understanding SQL Injection",
        resource_type="Article",
        duration_minutes=8,
        description="Plain-language explanation.",
        tag="Security",
        related_issue_type="Vulnerability",
        related_rule_key="java:S3649",
    )
    db.add(r)
    await db.flush()
    return r


@pytest.fixture
async def resource_smells(db: AsyncSession, user: User) -> LearningResource:
    r = LearningResource(
        id=uuid.uuid4(),
        title="Understanding Code Smells",
        resource_type="Article",
        duration_minutes=10,
        description="Quality basics.",
        tag="Quality",
        related_issue_type="CodeSmell",
        related_rule_key=None,
    )
    db.add(r)
    await db.flush()
    return r


@pytest.fixture
async def path_secure_java(db: AsyncSession, user: User) -> LearningPath:
    p = LearningPath(
        id=uuid.uuid4(),
        name="Secure Java Development",
        description="Secure coding for Java.",
        module_count=6,
    )
    db.add(p)
    await db.flush()
    return p


@pytest.fixture
async def path_progress(db: AsyncSession, user: User, path_secure_java: LearningPath) -> UserLearningProgress:
    prog = UserLearningProgress(
        id=uuid.uuid4(),
        user_id=user.id,
        path_id=path_secure_java.id,
        progress_pct=0.33,
    )
    db.add(prog)
    await db.flush()
    return prog


# ── Learning resources ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_resources_all(
    client: AsyncClient, user: User, auth_headers: dict,
    resource_sql: LearningResource, resource_smells: LearningResource,
):
    resp = await client.get("/api/v1/learning/resources", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    titles = {r["title"] for r in data}
    assert "Understanding SQL Injection" in titles
    assert "Understanding Code Smells" in titles


@pytest.mark.asyncio
async def test_list_resources_filter_issue_type(
    client: AsyncClient, user: User, auth_headers: dict,
    resource_sql: LearningResource, resource_smells: LearningResource,
):
    resp = await client.get(
        "/api/v1/learning/resources?issue_type=Vulnerability", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # Vulnerability resource comes first (relevance sort)
    assert data[0]["title"] == "Understanding SQL Injection"


@pytest.mark.asyncio
async def test_list_resources_filter_rule_key(
    client: AsyncClient, user: User, auth_headers: dict,
    resource_sql: LearningResource, resource_smells: LearningResource,
):
    resp = await client.get(
        "/api/v1/learning/resources?rule_key=java%3AS3649", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["title"] == "Understanding SQL Injection"


@pytest.mark.asyncio
async def test_list_resources_filter_tag(
    client: AsyncClient, user: User, auth_headers: dict,
    resource_sql: LearningResource, resource_smells: LearningResource,
):
    resp = await client.get("/api/v1/learning/resources?tag=Security", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert all(r["tag"] == "Security" for r in data)
    assert len(data) == 1


@pytest.mark.asyncio
async def test_list_resources_unauthenticated(client: AsyncClient, resource_sql: LearningResource):
    resp = await client.get("/api/v1/learning/resources")
    assert resp.status_code == 401


# ── Learning paths ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_paths_with_progress(
    client: AsyncClient, auth_headers: dict, db: AsyncSession,
    path_secure_java: LearningPath, resource_sql: LearningResource,
    user,
):
    """
    Path progress is derived from resource completions, not stored floats.
    Link resource_sql to path_secure_java, then complete it.
    Expected: progress_pct == 1.0 (1 completed / 1 linked).
    """
    # Link the resource to the path
    link = LearningPathResource(
        id=uuid.uuid4(),
        path_id=path_secure_java.id,
        resource_id=resource_sql.id,
        position=1,
    )
    db.add(link)
    await db.flush()

    # Mark it as completed by the test user
    await client.post(
        f"/api/v1/learning/resources/{resource_sql.id}/complete",
        headers=auth_headers,
    )

    resp = await client.get("/api/v1/learning/paths", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    p = data[0]
    assert p["name"] == "Secure Java Development"
    assert p["module_count"] == 1  # equals number of linked resources
    assert p["progress_pct"] == 1.0


@pytest.mark.asyncio
async def test_list_paths_no_progress(
    client: AsyncClient, auth_headers: dict, path_secure_java: LearningPath,
):
    """Path with no user progress record returns 0.0."""
    resp = await client.get("/api/v1/learning/paths", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["progress_pct"] == 0.0


@pytest.mark.asyncio
async def test_list_paths_unauthenticated(client: AsyncClient, path_secure_java: LearningPath):
    resp = await client.get("/api/v1/learning/paths")
    assert resp.status_code == 401


# ── Learning progress stats ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_progress_empty(client: AsyncClient, auth_headers: dict, user: User):
    resp = await client.get("/api/v1/learning/progress", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["resources_completed"] == 0
    assert data["resources_total"] == 0
    assert data["paths_started"] == 0
    assert data["total_study_minutes"] == 0


@pytest.mark.asyncio
async def test_progress_counts_paths_started(
    client: AsyncClient, auth_headers: dict,
    path_secure_java: LearningPath, path_progress: UserLearningProgress,
):
    resp = await client.get("/api/v1/learning/progress", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["paths_started"] == 1


# ── PATCH /auth/me ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_me_full_name(client: AsyncClient, user: User, auth_headers: dict):
    resp = await client.patch(
        "/api/v1/auth/me",
        json={"full_name": "Jane Smith"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["full_name"] == "Jane Smith"
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_patch_me_experience_level(client: AsyncClient, user: User, auth_headers: dict):
    resp = await client.patch(
        "/api/v1/auth/me",
        json={"experience_level": "advanced"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["experience_level"] == "advanced"


@pytest.mark.asyncio
async def test_patch_me_invalid_experience_level(client: AsyncClient, user: User, auth_headers: dict):
    resp = await client.patch(
        "/api/v1/auth/me",
        json={"experience_level": "expert"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_me_empty_full_name_rejected(client: AsyncClient, user: User, auth_headers: dict):
    resp = await client.patch(
        "/api/v1/auth/me",
        json={"full_name": ""},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_me_unauthenticated(client: AsyncClient):
    resp = await client.patch("/api/v1/auth/me", json={"full_name": "Hacker"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_patch_me_no_password_hash_in_response(client: AsyncClient, user: User, auth_headers: dict):
    resp = await client.patch(
        "/api/v1/auth/me",
        json={"department": "Engineering"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "password_hash" not in resp.json()
    assert "password" not in str(resp.json())


# ── POST /learning/resources/{id}/complete ────────────────────────────────────

@pytest.mark.asyncio
async def test_complete_resource_success(
    client: AsyncClient, auth_headers: dict, resource_sql: LearningResource,
):
    resp = await client.post(
        f"/api/v1/learning/resources/{resource_sql.id}/complete",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["completed"] is True
    assert data["resource_id"] == str(resource_sql.id)


@pytest.mark.asyncio
async def test_complete_resource_idempotent(
    client: AsyncClient, auth_headers: dict, resource_sql: LearningResource,
):
    """Calling complete twice must not create duplicate records and must return 200 both times."""
    r1 = await client.post(
        f"/api/v1/learning/resources/{resource_sql.id}/complete", headers=auth_headers
    )
    r2 = await client.post(
        f"/api/v1/learning/resources/{resource_sql.id}/complete", headers=auth_headers
    )
    assert r1.status_code == 200
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_complete_resource_updates_progress_count(
    client: AsyncClient, auth_headers: dict, resource_sql: LearningResource,
):
    before = (await client.get("/api/v1/learning/progress", headers=auth_headers)).json()
    await client.post(
        f"/api/v1/learning/resources/{resource_sql.id}/complete", headers=auth_headers
    )
    after = (await client.get("/api/v1/learning/progress", headers=auth_headers)).json()
    assert after["resources_completed"] == before["resources_completed"] + 1


@pytest.mark.asyncio
async def test_complete_resource_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        f"/api/v1/learning/resources/{uuid.uuid4()}/complete",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_complete_resource_unauthenticated(
    client: AsyncClient, resource_sql: LearningResource,
):
    resp = await client.post(f"/api/v1/learning/resources/{resource_sql.id}/complete")
    assert resp.status_code == 401
