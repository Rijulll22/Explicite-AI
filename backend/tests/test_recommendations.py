"""
Tests for learning-recommendation endpoints (Batch H FR-LEARN-01, FR-LEARN-06)
and the recommendation service unit logic.

Endpoints under test:
  GET /api/v1/projects/{project_id}/issues/{issue_id}/learning
  GET /api/v1/projects/{project_id}/learning/recommend
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from types import SimpleNamespace

from app.models.analysis import AnalysisJob
from app.models.finding import Finding
from app.models.learning import LearningResource, UserLearningProgress
from app.models.project import Project, ProjectMembership
from app.models.user import User
from app.services.recommendation_service import (
    ResourceMatch,
    _match_score_and_reason,
    recommend_for_finding,
    recommend_for_project,
)


# ── Helpers ────────────────────────────────────────────────────────────────────
# Use SimpleNamespace instead of SQLAlchemy model instances so the unit tests
# don't depend on a database session or ORM instrumentation.

def _mock_finding(
    rule_key: str | None = "java:S3649",
    issue_type: str = "Vulnerability",
    risk_score: float = 5.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        rule_key=rule_key,
        issue_type=issue_type,
        risk_score=risk_score,
        title="Test Finding",
        status="Open",
    )


def _mock_resource(
    related_rule_key: str | None = None,
    related_issue_type: str | None = None,
    tag: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        related_rule_key=related_rule_key,
        related_issue_type=related_issue_type,
        tag=tag,
    )


# ── Unit tests: _match_score_and_reason ───────────────────────────────────────

class TestMatchScoreAndReason:
    def test_rule_key_match_gives_score_3(self):
        f = _mock_finding(rule_key="java:S3649")
        r = _mock_resource(related_rule_key="java:S3649")
        result = _match_score_and_reason(f, r)
        assert result is not None
        score, reason = result
        assert score == 3
        assert "java:S3649" in reason

    def test_issue_type_match_gives_score_2(self):
        f = _mock_finding(rule_key=None, issue_type="Vulnerability")
        r = _mock_resource(related_issue_type="Vulnerability")
        result = _match_score_and_reason(f, r)
        assert result is not None
        score, _ = result
        assert score == 2

    def test_security_tag_match_for_vulnerability(self):
        f = _mock_finding(rule_key=None, issue_type="Vulnerability")
        r = _mock_resource(tag="Security")
        result = _match_score_and_reason(f, r)
        assert result is not None
        score, _ = result
        assert score == 1

    def test_quality_tag_match_for_code_smell(self):
        f = _mock_finding(rule_key=None, issue_type="Code Smell")
        r = _mock_resource(tag="Quality")
        result = _match_score_and_reason(f, r)
        assert result is not None
        score, _ = result
        assert score == 1

    def test_no_match_returns_none(self):
        f = _mock_finding(rule_key="java:S3649", issue_type="Vulnerability")
        r = _mock_resource(related_rule_key="java:S9999", related_issue_type="Code Smell")
        result = _match_score_and_reason(f, r)
        assert result is None

    def test_rule_key_beats_issue_type(self):
        # A resource with a rule_key match scores 3; one with issue_type scores 2
        f = _mock_finding(rule_key="java:S3649", issue_type="Vulnerability")
        r_rule = _mock_resource(related_rule_key="java:S3649")
        r_type = _mock_resource(related_issue_type="Vulnerability")
        s1, _ = _match_score_and_reason(f, r_rule)
        s2, _ = _match_score_and_reason(f, r_type)
        assert s1 > s2

    def test_security_tag_not_matched_for_code_smell(self):
        f = _mock_finding(rule_key=None, issue_type="Code Smell")
        r = _mock_resource(tag="Security")
        assert _match_score_and_reason(f, r) is None

    def test_quality_tag_not_matched_for_vulnerability(self):
        f = _mock_finding(rule_key=None, issue_type="Vulnerability")
        r = _mock_resource(tag="Quality")
        assert _match_score_and_reason(f, r) is None


# ── Unit tests: recommend_for_finding ─────────────────────────────────────────

class TestRecommendForFinding:
    def test_returns_matches_ordered_by_score(self):
        f = _mock_finding(rule_key="java:S3649", issue_type="Vulnerability")
        r_rule = _mock_resource(related_rule_key="java:S3649")
        r_type = _mock_resource(related_issue_type="Vulnerability")
        r_none = _mock_resource(related_issue_type="Code Smell")

        matches = recommend_for_finding(f, [r_none, r_type, r_rule], completed_ids=set())
        assert len(matches) == 2
        assert matches[0].resource is r_rule
        assert matches[1].resource is r_type

    def test_marks_completed_resources(self):
        f = _mock_finding(rule_key="java:S3649")
        r = _mock_resource(related_rule_key="java:S3649")
        matches = recommend_for_finding(f, [r], completed_ids={r.id})
        assert matches[0].is_completed is True

    def test_returns_empty_for_no_match(self):
        # Security Hotspot findings don't match Quality-tagged resources
        f = _mock_finding(rule_key=None, issue_type="Security Hotspot")
        r = _mock_resource(tag="Quality")
        matches = recommend_for_finding(f, [r], completed_ids=set())
        assert matches == []

    def test_no_duplicate_resources(self):
        f = _mock_finding(rule_key="java:S3649", issue_type="Vulnerability")
        r = _mock_resource(related_rule_key="java:S3649", related_issue_type="Vulnerability")
        matches = recommend_for_finding(f, [r], completed_ids=set())
        assert len(matches) == 1


# ── Unit tests: recommend_for_project ─────────────────────────────────────────

class TestRecommendForProject:
    def test_empty_findings_returns_empty(self):
        r = _mock_resource(tag="Security")
        assert recommend_for_project([], [r], completed_ids=set()) == []

    def test_completed_resources_deprioritised(self):
        f = _mock_finding(rule_key="java:S3649", issue_type="Vulnerability", risk_score=5.0)
        r_rule = _mock_resource(related_rule_key="java:S3649")
        r_type = _mock_resource(related_issue_type="Vulnerability")
        # r_rule is completed; r_type is not
        completed = {r_rule.id}
        matches = recommend_for_project([f], [r_rule, r_type], completed_ids=completed)
        # Uncompleted r_type must come first
        assert not matches[0].is_completed
        assert matches[0].resource is r_type

    def test_risk_score_weights_ranking(self):
        # Two findings matching different resources; high-risk finding wins
        f_high = _mock_finding(rule_key="java:S3649", risk_score=9.0)
        f_low  = _mock_finding(rule_key="java:S1234", risk_score=1.0)
        r_high = _mock_resource(related_rule_key="java:S3649")
        r_low  = _mock_resource(related_rule_key="java:S1234")
        matches = recommend_for_project([f_high, f_low], [r_high, r_low], completed_ids=set())
        assert matches[0].resource is r_high

    def test_max_results_respected(self):
        f = _mock_finding(rule_key=None, issue_type="Vulnerability")
        resources = [_mock_resource(related_issue_type="Vulnerability") for _ in range(15)]
        matches = recommend_for_project([f], resources, completed_ids=set(), max_results=5)
        assert len(matches) <= 5


# ── Integration tests ─────────────────────────────────────────────────────────

@pytest.fixture
async def project_with_finding(db: AsyncSession, user: User):
    project = Project(
        id=uuid.uuid4(),
        name="Rec Test Project",
        owner_id=user.id,
        default_branch="main",
    )
    db.add(project)
    await db.flush()

    db.add(ProjectMembership(project_id=project.id, user_id=user.id, role="developer"))

    job = AnalysisJob(
        id=uuid.uuid4(),
        project_id=project.id,
        status="completed",
        source_branch="main",
    )
    db.add(job)
    await db.flush()

    finding = Finding(
        id=uuid.uuid4(),
        project_id=project.id,
        analysis_job_id=job.id,
        engine_severity="Critical",
        risk_level="High",
        risk_score=9.1,
        risk_score_version="v1.0",
        issue_type="Vulnerability",
        title="SQL Injection",
        rule_key="java:S3649",
        file_path="Foo.java",
        line_number=42,
        status="Open",
    )
    db.add(finding)
    await db.flush()
    return project, finding


@pytest.fixture
async def resource_matching(db: AsyncSession) -> LearningResource:
    r = LearningResource(
        id=uuid.uuid4(),
        title="SQL Injection Guide",
        resource_type="Article",
        duration_minutes=8,
        tag="Security",
        related_issue_type="Vulnerability",
        related_rule_key="java:S3649",
    )
    db.add(r)
    await db.flush()
    return r


@pytest.fixture
async def resource_unrelated(db: AsyncSession) -> LearningResource:
    r = LearningResource(
        id=uuid.uuid4(),
        title="Unrelated Resource",
        resource_type="Article",
        duration_minutes=5,
        tag="Quality",
        related_issue_type=None,
        related_rule_key=None,
    )
    db.add(r)
    await db.flush()
    return r


class TestRecommendForIssue:
    @pytest.mark.asyncio
    async def test_returns_matched_resources(
        self,
        client: AsyncClient,
        auth_headers: dict,
        project_with_finding,
        resource_matching: LearningResource,
        resource_unrelated: LearningResource,
    ):
        project, finding = project_with_finding
        resp = await client.get(
            f"/api/v1/projects/{project.id}/issues/{finding.id}/learning",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        ids = [d["id"] for d in data]
        assert str(resource_matching.id) in ids
        assert str(resource_unrelated.id) not in ids

    @pytest.mark.asyncio
    async def test_match_reason_present(
        self,
        client: AsyncClient,
        auth_headers: dict,
        project_with_finding,
        resource_matching: LearningResource,
    ):
        project, finding = project_with_finding
        resp = await client.get(
            f"/api/v1/projects/{project.id}/issues/{finding.id}/learning",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        matched = next((d for d in data if d["id"] == str(resource_matching.id)), None)
        assert matched is not None
        assert len(matched["match_reason"]) > 0
        assert "java:S3649" in matched["match_reason"]

    @pytest.mark.asyncio
    async def test_completed_flag_set(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db: AsyncSession,
        user: User,
        project_with_finding,
        resource_matching: LearningResource,
    ):
        project, finding = project_with_finding
        # Complete the resource first
        prog = UserLearningProgress(
            id=uuid.uuid4(),
            user_id=user.id,
            resource_id=resource_matching.id,
            progress_pct=1.0,
            completed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        db.add(prog)
        await db.flush()

        resp = await client.get(
            f"/api/v1/projects/{project.id}/issues/{finding.id}/learning",
            headers=auth_headers,
        )
        data = resp.json()
        matched = next(d for d in data if d["id"] == str(resource_matching.id))
        assert matched["is_completed"] is True

    @pytest.mark.asyncio
    async def test_empty_when_no_match(
        self,
        client: AsyncClient,
        auth_headers: dict,
        project_with_finding,
        resource_unrelated: LearningResource,
    ):
        project, finding = project_with_finding
        resp = await client.get(
            f"/api/v1/projects/{project.id}/issues/{finding.id}/learning",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        # resource_unrelated does not match the finding; only it exists
        ids = [d["id"] for d in resp.json()]
        assert str(resource_unrelated.id) not in ids

    @pytest.mark.asyncio
    async def test_requires_authentication(
        self,
        client: AsyncClient,
        project_with_finding,
    ):
        project, finding = project_with_finding
        resp = await client.get(
            f"/api/v1/projects/{project.id}/issues/{finding.id}/learning"
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_project_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        project_with_finding,
    ):
        _project, finding = project_with_finding
        fake_project_id = uuid.uuid4()
        resp = await client.get(
            f"/api/v1/projects/{fake_project_id}/issues/{finding.id}/learning",
            headers=auth_headers,
        )
        assert resp.status_code in (403, 404)

    @pytest.mark.asyncio
    async def test_finding_from_different_project_blocked(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db: AsyncSession,
        user: User,
        project_with_finding,
    ):
        """Finding ID from another project must not leak through the recommendation endpoint."""
        other_project = Project(
            id=uuid.uuid4(),
            name="Other Project",
            owner_id=user.id,
            default_branch="main",
        )
        db.add(other_project)
        membership = ProjectMembership(
            project_id=other_project.id, user_id=user.id, role="developer"
        )
        db.add(membership)

        real_project, real_finding = project_with_finding
        await db.flush()

        # Try to retrieve the real_finding via other_project
        resp = await client.get(
            f"/api/v1/projects/{other_project.id}/issues/{real_finding.id}/learning",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestPersonalisedRecommendations:
    @pytest.mark.asyncio
    async def test_returns_recommendations_for_project(
        self,
        client: AsyncClient,
        auth_headers: dict,
        project_with_finding,
        resource_matching: LearningResource,
    ):
        project, _finding = project_with_finding
        resp = await client.get(
            f"/api/v1/projects/{project.id}/learning/recommend",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        ids = [d["id"] for d in data]
        assert str(resource_matching.id) in ids

    @pytest.mark.asyncio
    async def test_empty_when_no_findings(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db: AsyncSession,
        user: User,
        resource_matching: LearningResource,
    ):
        # Project with no findings
        empty_project = Project(
            id=uuid.uuid4(),
            name="Empty Project",
            owner_id=user.id,
            default_branch="main",
        )
        db.add(empty_project)
        db.add(ProjectMembership(
            project_id=empty_project.id, user_id=user.id, role="developer"
        ))
        await db.flush()

        resp = await client.get(
            f"/api/v1/projects/{empty_project.id}/learning/recommend",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_completed_resources_deprioritised(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db: AsyncSession,
        user: User,
        project_with_finding,
        resource_matching: LearningResource,
    ):
        project, _finding = project_with_finding
        # Complete resource_matching
        prog = UserLearningProgress(
            id=uuid.uuid4(),
            user_id=user.id,
            resource_id=resource_matching.id,
            progress_pct=1.0,
            completed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        db.add(prog)
        await db.flush()

        resp = await client.get(
            f"/api/v1/projects/{project.id}/learning/recommend",
            headers=auth_headers,
        )
        data = resp.json()
        assert resp.status_code == 200
        matched = next((d for d in data if d["id"] == str(resource_matching.id)), None)
        # It must still appear but flagged as completed
        assert matched is not None
        assert matched["is_completed"] is True

    @pytest.mark.asyncio
    async def test_requires_authentication(
        self,
        client: AsyncClient,
        project_with_finding,
    ):
        project, _ = project_with_finding
        resp = await client.get(f"/api/v1/projects/{project.id}/learning/recommend")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_cross_project_isolation(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db: AsyncSession,
        user: User,
        project_with_finding,
    ):
        """User cannot see another user's project recommendations."""
        other_user = User(
            id=uuid.uuid4(),
            email="other@example.com",
            password_hash="x",
            full_name="Other User",
            system_role="member",
        )
        db.add(other_user)
        other_project = Project(
            id=uuid.uuid4(),
            name="Other User Project",
            owner_id=other_user.id,
            default_branch="main",
        )
        db.add(other_project)
        await db.flush()

        resp = await client.get(
            f"/api/v1/projects/{other_project.id}/learning/recommend",
            headers=auth_headers,
        )
        assert resp.status_code in (403, 404)

    @pytest.mark.asyncio
    async def test_resolved_findings_excluded(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db: AsyncSession,
        user: User,
        resource_matching: LearningResource,
    ):
        """Resolved findings must not contribute to personalised recommendations."""
        project = Project(
            id=uuid.uuid4(),
            name="Resolved Project",
            owner_id=user.id,
            default_branch="main",
        )
        db.add(project)
        db.add(ProjectMembership(
            project_id=project.id, user_id=user.id, role="developer"
        ))
        job = AnalysisJob(
            id=uuid.uuid4(), project_id=project.id,
            status="completed", source_branch="main",
        )
        db.add(job)
        await db.flush()

        resolved_finding = Finding(
            id=uuid.uuid4(),
            project_id=project.id,
            analysis_job_id=job.id,
            engine_severity="Critical",
            risk_level="High",
            risk_score=9.1,
            risk_score_version="v1.0",
            issue_type="Vulnerability",
            title="Resolved SQL Injection",
            rule_key="java:S3649",
            file_path="Foo.java",
            line_number=42,
            status="Resolved",  # Resolved — must be excluded
        )
        db.add(resolved_finding)
        await db.flush()

        resp = await client.get(
            f"/api/v1/projects/{project.id}/learning/recommend",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ── progress endpoint includes completed_resource_ids ─────────────────────────

@pytest.mark.asyncio
async def test_progress_includes_completed_resource_ids(
    client: AsyncClient,
    auth_headers: dict,
    resource_matching: LearningResource,
):
    """GET /learning/progress must return completed_resource_ids after a completion."""
    await client.post(
        f"/api/v1/learning/resources/{resource_matching.id}/complete",
        headers=auth_headers,
    )
    resp = await client.get("/api/v1/learning/progress", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "completed_resource_ids" in data
    assert str(resource_matching.id) in data["completed_resource_ids"]


@pytest.mark.asyncio
async def test_progress_completed_ids_empty_initially(
    client: AsyncClient,
    auth_headers: dict,
):
    resp = await client.get("/api/v1/learning/progress", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "completed_resource_ids" in data
    assert data["completed_resource_ids"] == []
