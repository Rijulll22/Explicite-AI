"""
Test fixtures.

Tests run against a separate PostgreSQL database (TEST_DATABASE_URL).
Tables are created once per session and truncated between tests (autouse fixture).
The FastAPI dependency get_db is overridden to use the test session factory.
"""
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure .env is loaded before settings are imported (pydantic-settings reads it
# automatically, but only if the CWD is the backend root when pytest starts).
os.environ.setdefault("_TESTS_RUNNING", "1")

from app.config import settings  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.database import Base, get_db, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.analysis import AnalysisJob  # noqa: E402
from app.models.finding import Finding  # noqa: E402
from app.models.project import Project, ProjectMembership  # noqa: E402
from app.models.user import User  # noqa: E402

# ── Test database engine ───────────────────────────────────────────────────────

_TEST_DB_URL = settings.TEST_DATABASE_URL or settings.DATABASE_URL.replace(
    "/explicite_ai", "/test_explicite_ai"
)

_test_engine = create_async_engine(_TEST_DB_URL, echo=False, pool_pre_ping=True)
_TestSessionFactory = async_sessionmaker(_test_engine, expire_on_commit=False)


# ── Session-scoped: create / drop all tables ───────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
async def setup_test_db():
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _test_engine.dispose()


# ── Function-scoped: truncate all tables after every test ─────────────────────

@pytest.fixture(autouse=True)
async def truncate_tables(setup_test_db):
    yield
    async with _test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


# ── DB session & app client ────────────────────────────────────────────────────

@pytest.fixture
async def db() -> AsyncSession:
    async with _TestSessionFactory() as session:
        yield session
        await session.commit()


@pytest.fixture
async def client(db: AsyncSession) -> AsyncClient:
    """
    HTTP test client with get_db overridden to use the test session.
    Also initialises the app DB engine to the test database so that
    startup code does not try to connect to the production DB.
    """
    init_db(_TEST_DB_URL)

    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as c:
        yield c
    app.dependency_overrides.clear()


# ── Common data fixtures ───────────────────────────────────────────────────────

@pytest.fixture
async def user(db: AsyncSession) -> User:
    u = User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash=hash_password("testpassword"),
        full_name="Test User",
        system_role="member",
        is_email_verified=True,
        is_active=True,
    )
    db.add(u)
    await db.flush()
    return u


@pytest.fixture
async def second_user(db: AsyncSession) -> User:
    u = User(
        id=uuid.uuid4(),
        email="other@example.com",
        password_hash=hash_password("otherpassword"),
        full_name="Other User",
        system_role="member",
        is_email_verified=True,
        is_active=True,
    )
    db.add(u)
    await db.flush()
    return u


@pytest.fixture
async def project(db: AsyncSession, user: User) -> Project:
    p = Project(
        id=uuid.uuid4(),
        name="Test Project",
        default_branch="main",
        owner_id=user.id,
    )
    db.add(p)
    membership = ProjectMembership(project_id=p.id, user_id=user.id, role="owner")
    db.add(membership)
    await db.flush()
    return p


@pytest.fixture
async def analysis_job(db: AsyncSession, project: Project) -> AnalysisJob:
    from datetime import datetime, timezone

    job = AnalysisJob(
        id=uuid.uuid4(),
        project_id=project.id,
        status="completed",
        source_branch="main",
        quality_gate_passed=False,
        bugs_count=3,
        vulnerabilities_count=1,
        code_smells_count=5,
        security_hotspots_count=2,
        coverage_pct=64.0,
        duplications_pct=8.3,
        technical_debt_minutes=1200,
        completed_at=datetime.now(tz=timezone.utc),
    )
    db.add(job)
    await db.flush()
    return job


@pytest.fixture
async def finding(db: AsyncSession, project: Project, analysis_job: AnalysisJob) -> Finding:
    f = Finding(
        id=uuid.uuid4(),
        analysis_job_id=analysis_job.id,
        project_id=project.id,
        engine_severity="Critical",
        risk_level="High",
        issue_type="Vulnerability",
        title="SQL Injection",
        rule_key="java:S3649",
        file_path="StudentDAO.java",
        line_number=42,
        status="Open",
        cwe_id="CWE-89",
        owasp_category="A03:2021",
        cvss_score=9.1,
    )
    db.add(f)
    await db.flush()
    return f


@pytest.fixture
def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}
