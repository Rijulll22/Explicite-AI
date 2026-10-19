"""
Tests for the AI tutor endpoints:
  POST /learning/tutor/start
  POST /learning/tutor/{session_id}/chat

Covers: session creation, idempotency, message persistence, conversation context,
cross-user isolation, authentication, AI-unavailable errors, message-length limits.
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.learning import LearningResource, TutorMessage, TutorSession
from app.models.user import User


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
async def resource(db: AsyncSession) -> LearningResource:
    r = LearningResource(
        id=uuid.uuid4(),
        title="Understanding SQL Injection",
        resource_type="Article",
        duration_minutes=15,
        description="Learn how SQL injection attacks work and how to prevent them.",
        tag="Security",
        related_issue_type="Vulnerability",
        related_rule_key="java:S3649",
    )
    db.add(r)
    await db.flush()
    return r


@pytest.fixture
async def resource2(db: AsyncSession) -> LearningResource:
    r = LearningResource(
        id=uuid.uuid4(),
        title="Input Validation Best Practices",
        resource_type="Guide",
        duration_minutes=20,
        description="Techniques for validating and sanitising user input.",
        tag="Security",
        related_issue_type="Vulnerability",
    )
    db.add(r)
    await db.flush()
    return r


# ── POST /learning/tutor/start ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_creates_session(
    client: AsyncClient,
    resource: LearningResource,
    auth_headers: dict,
):
    resp = await client.post(
        "/api/v1/learning/tutor/start",
        json={"resource_id": str(resource.id)},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["resource"]["id"] == str(resource.id)
    assert data["resource"]["title"] == "Understanding SQL Injection"
    assert data["messages"] == []


@pytest.mark.asyncio
async def test_start_is_idempotent(
    client: AsyncClient,
    resource: LearningResource,
    auth_headers: dict,
):
    resp1 = await client.post(
        "/api/v1/learning/tutor/start",
        json={"resource_id": str(resource.id)},
        headers=auth_headers,
    )
    resp2 = await client.post(
        "/api/v1/learning/tutor/start",
        json={"resource_id": str(resource.id)},
        headers=auth_headers,
    )
    assert resp1.status_code == resp2.status_code == 200
    assert resp1.json()["session_id"] == resp2.json()["session_id"]


@pytest.mark.asyncio
async def test_start_requires_auth(client: AsyncClient, resource: LearningResource):
    resp = await client.post(
        "/api/v1/learning/tutor/start",
        json={"resource_id": str(resource.id)},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_start_unknown_resource(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/learning/tutor/start",
        json={"resource_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_start_returns_existing_messages(
    client: AsyncClient,
    db: AsyncSession,
    resource: LearningResource,
    user: User,
    auth_headers: dict,
):
    """If the session already has messages, start returns them."""
    session = TutorSession(
        id=uuid.uuid4(), user_id=user.id, resource_id=resource.id
    )
    db.add(session)
    await db.flush()
    msg = TutorMessage(
        id=uuid.uuid4(), session_id=session.id, role="user", content="Hi!"
    )
    db.add(msg)
    await db.commit()

    resp = await client.post(
        "/api/v1/learning/tutor/start",
        json={"resource_id": str(resource.id)},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == str(session.id)
    assert len(data["messages"]) == 1
    assert data["messages"][0]["content"] == "Hi!"


# ── POST /learning/tutor/{session_id}/chat ─────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_returns_ai_reply(
    client: AsyncClient,
    db: AsyncSession,
    resource: LearningResource,
    user: User,
    auth_headers: dict,
):
    session = TutorSession(
        id=uuid.uuid4(), user_id=user.id, resource_id=resource.id
    )
    db.add(session)
    await db.commit()

    with patch(
        "app.api.learning.get_provider",
        return_value=_make_mock_provider("SQL injection is a vulnerability."),
    ):
        resp = await client.post(
            f"/api/v1/learning/tutor/{session.id}/chat",
            json={"message": "What is SQL injection?"},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["message"]["role"] == "assistant"
    assert data["message"]["content"] == "SQL injection is a vulnerability."
    assert data["message"]["session_id"] == str(session.id)


@pytest.mark.asyncio
async def test_chat_persists_user_and_assistant_messages(
    client: AsyncClient,
    db: AsyncSession,
    resource: LearningResource,
    user: User,
    auth_headers: dict,
):
    session = TutorSession(
        id=uuid.uuid4(), user_id=user.id, resource_id=resource.id
    )
    db.add(session)
    await db.commit()

    with patch(
        "app.api.learning.get_provider",
        return_value=_make_mock_provider("Here is an explanation."),
    ):
        await client.post(
            f"/api/v1/learning/tutor/{session.id}/chat",
            json={"message": "Explain SQL injection"},
            headers=auth_headers,
        )

    from sqlalchemy import select
    msgs_result = await db.execute(
        select(TutorMessage)
        .where(TutorMessage.session_id == session.id)
        .order_by(TutorMessage.created_at)
    )
    msgs = msgs_result.scalars().all()
    assert len(msgs) == 2
    assert msgs[0].role == "user"
    assert msgs[0].content == "Explain SQL injection"
    assert msgs[1].role == "assistant"
    assert msgs[1].content == "Here is an explanation."


@pytest.mark.asyncio
async def test_chat_conversation_history_preserved(
    client: AsyncClient,
    db: AsyncSession,
    resource: LearningResource,
    user: User,
    auth_headers: dict,
):
    """On the second turn the conversation history is non-empty."""
    session = TutorSession(
        id=uuid.uuid4(), user_id=user.id, resource_id=resource.id
    )
    db.add(session)
    await db.commit()

    captured: list[list] = []

    def _factory(reply: str):
        provider = AsyncMock()
        async def _multi_turn(system, history, user_msg):
            captured.append(list(history))
            return reply
        provider.chat_multi_turn = _multi_turn
        return provider

    with patch("app.api.learning.get_provider", return_value=_factory("First reply")):
        await client.post(
            f"/api/v1/learning/tutor/{session.id}/chat",
            json={"message": "Turn one"},
            headers=auth_headers,
        )

    with patch("app.api.learning.get_provider", return_value=_factory("Second reply")):
        await client.post(
            f"/api/v1/learning/tutor/{session.id}/chat",
            json={"message": "Turn two"},
            headers=auth_headers,
        )

    # Second call should have history (turn-one user + turn-one assistant)
    assert len(captured) == 2
    assert captured[0] == []                     # first turn: no prior history
    assert len(captured[1]) == 2                 # second turn: user + assistant
    assert captured[1][0]["role"] == "user"
    assert captured[1][0]["content"] == "Turn one"
    assert captured[1][1]["role"] == "assistant"
    assert captured[1][1]["content"] == "First reply"


@pytest.mark.asyncio
async def test_chat_requires_auth(
    client: AsyncClient,
    db: AsyncSession,
    resource: LearningResource,
    user: User,
):
    session = TutorSession(
        id=uuid.uuid4(), user_id=user.id, resource_id=resource.id
    )
    db.add(session)
    await db.commit()

    resp = await client.post(
        f"/api/v1/learning/tutor/{session.id}/chat",
        json={"message": "hello"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_chat_cross_user_isolation(
    client: AsyncClient,
    db: AsyncSession,
    resource: LearningResource,
    user: User,
    second_user: User,
):
    """second_user must not access user's session."""
    session = TutorSession(
        id=uuid.uuid4(), user_id=user.id, resource_id=resource.id
    )
    db.add(session)
    await db.commit()

    token = create_access_token(subject=str(second_user.id))
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        f"/api/v1/learning/tutor/{session.id}/chat",
        json={"message": "Snoop"},
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_chat_unknown_session(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        f"/api/v1/learning/tutor/{uuid.uuid4()}/chat",
        json={"message": "hello"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_chat_message_too_long(
    client: AsyncClient,
    db: AsyncSession,
    resource: LearningResource,
    user: User,
    auth_headers: dict,
):
    session = TutorSession(
        id=uuid.uuid4(), user_id=user.id, resource_id=resource.id
    )
    db.add(session)
    await db.commit()

    resp = await client.post(
        f"/api/v1/learning/tutor/{session.id}/chat",
        json={"message": "x" * 2001},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_chat_ai_unavailable_stores_user_message(
    client: AsyncClient,
    db: AsyncSession,
    resource: LearningResource,
    user: User,
    auth_headers: dict,
):
    """User message is persisted even when the AI provider is unavailable."""
    from app.services.ai_service import AiUnavailableError

    session = TutorSession(
        id=uuid.uuid4(), user_id=user.id, resource_id=resource.id
    )
    db.add(session)
    await db.commit()

    provider = AsyncMock()
    provider.chat_multi_turn = AsyncMock(
        side_effect=AiUnavailableError("Ollama not running")
    )

    with patch("app.api.learning.get_provider", return_value=provider):
        resp = await client.post(
            f"/api/v1/learning/tutor/{session.id}/chat",
            json={"message": "What is SQL injection?"},
            headers=auth_headers,
        )

    assert resp.status_code == 503
    assert "Ollama" in resp.json()["detail"]

    # User message must still be in DB
    from sqlalchemy import select
    msgs_result = await db.execute(
        select(TutorMessage).where(TutorMessage.session_id == session.id)
    )
    msgs = msgs_result.scalars().all()
    assert len(msgs) == 1
    assert msgs[0].role == "user"
    assert msgs[0].content == "What is SQL injection?"


@pytest.mark.asyncio
async def test_chat_empty_message_rejected(
    client: AsyncClient,
    db: AsyncSession,
    resource: LearningResource,
    user: User,
    auth_headers: dict,
):
    session = TutorSession(
        id=uuid.uuid4(), user_id=user.id, resource_id=resource.id
    )
    db.add(session)
    await db.commit()

    resp = await client.post(
        f"/api/v1/learning/tutor/{session.id}/chat",
        json={"message": ""},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_start_sessions_are_per_user(
    client: AsyncClient,
    resource: LearningResource,
    user: User,
    second_user: User,
):
    """Two users starting the same resource get separate sessions."""
    token1 = create_access_token(subject=str(user.id))
    token2 = create_access_token(subject=str(second_user.id))

    resp1 = await client.post(
        "/api/v1/learning/tutor/start",
        json={"resource_id": str(resource.id)},
        headers={"Authorization": f"Bearer {token1}"},
    )
    resp2 = await client.post(
        "/api/v1/learning/tutor/start",
        json={"resource_id": str(resource.id)},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp1.status_code == resp2.status_code == 200
    assert resp1.json()["session_id"] != resp2.json()["session_id"]


# ── Helper ─────────────────────────────────────────────────────────────────────

def _make_mock_provider(reply: str):
    provider = AsyncMock()
    provider.chat_multi_turn = AsyncMock(return_value=reply)
    provider.__class__.__name__ = "OllamaProvider"
    return provider
