"""
Tests for POST /api/v1/auth/login and GET /api/v1/auth/me.

Coverage:
- Correct credentials → token + user profile
- Wrong password → 401
- Unknown email → 401
- Inactive account → 401
- Password hash not exposed in any response
- /me with valid token
- /me with missing/invalid token → 401
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.user import User


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, user: User):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "testpassword"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    assert data["user"]["email"] == "test@example.com"
    assert data["user"]["full_name"] == "Test User"
    assert "password_hash" not in data["user"]
    assert "password" not in str(data)


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, user: User):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "irrelevant"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(client: AsyncClient, db: AsyncSession):
    inactive = User(
        id=uuid.uuid4(),
        email="inactive@example.com",
        password_hash=hash_password("pass"),
        full_name="Inactive",
        system_role="member",
        is_active=False,
        is_email_verified=True,
    )
    db.add(inactive)
    await db.flush()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@example.com", "password": "pass"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_empty_password(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": ""},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_me_authenticated(client: AsyncClient, user: User, auth_headers: dict):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_me_no_token(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_invalid_token(client: AsyncClient):
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer this.is.not.valid"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_deleted_user_token(client: AsyncClient, db: AsyncSession):
    """A valid JWT whose subject no longer exists should be rejected."""
    ghost_id = str(uuid.uuid4())
    token = create_access_token(subject=ghost_id)
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401
