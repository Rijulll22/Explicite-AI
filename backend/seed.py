"""
Seed the database with data that exactly mirrors frontend/src/data.ts.

Safe to re-run: uses INSERT ... ON CONFLICT DO NOTHING so existing rows are
preserved and no duplicates are created.

Usage (from the backend/ directory):
    py seed.py
"""
import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

# Load .env
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.models.user import User
from app.models.project import Project, ProjectMembership
from app.models.analysis import AnalysisJob
from app.models.finding import Finding
from app.models.learning import LearningResource, LearningPath, LearningPathResource, UserLearningProgress
from app.database import Base

DATABASE_URL = os.environ["DATABASE_URL"]

# ── Stable UUIDs — derived deterministically so re-runs are idempotent ────────
# Using uuid5 (namespace + name) ensures the same UUID every run.
_NS = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _uid(name: str) -> uuid.UUID:
    return uuid.uuid5(_NS, name)


# ── Reference data ─────────────────────────────────────────────────────────────

USER_ID = _uid("jane.doe")
USER_EMAIL = "jane.doe@university.ac.uk"

# Projects — matches data.ts exactly
PROJECTS = [
    {
        "id": _uid("project.sms"),
        "name": "Student Management System",
        "quality_gate_passed": False,
        "bugs": 12,
        "vulnerabilities": 3,
        "code_smells": 24,
        "security_hotspots": 5,
        "coverage_pct": 64.0,
        "duplications_pct": 8.3,
        "technical_debt_minutes": 1560 + 120,  # 3d 2h in 8h days: (3*8+2)*60 = 1560+120
        "branch": "main",
        "offset_hours": 2,  # "2 hours ago"
    },
    {
        "id": _uid("project.library"),
        "name": "Library Catalogue System",
        "quality_gate_passed": True,
        "bugs": 4,
        "vulnerabilities": 0,
        "code_smells": 8,
        "security_hotspots": 0,
        "coverage_pct": 78.0,
        "duplications_pct": 3.1,
        "technical_debt_minutes": 240,
        "branch": "main",
        "offset_hours": 24,  # "1 day ago"
    },
    {
        "id": _uid("project.exam"),
        "name": "Online Exam Portal",
        "quality_gate_passed": True,
        "bugs": 7,
        "vulnerabilities": 1,
        "code_smells": 15,
        "security_hotspots": 2,
        "coverage_pct": 71.0,
        "duplications_pct": 5.4,
        "technical_debt_minutes": 360,
        "branch": "develop",
        "offset_hours": 72,  # "3 days ago"
    },
    {
        "id": _uid("project.attendance"),
        "name": "Attendance Tracker",
        "quality_gate_passed": False,
        "bugs": 2,
        "vulnerabilities": 2,
        "code_smells": 6,
        "security_hotspots": 1,
        "coverage_pct": 55.0,
        "duplications_pct": 6.2,
        "technical_debt_minutes": 480,
        "branch": "main",
        "offset_hours": 120,  # "5 days ago"
    },
]

# Issues — matches data.ts exactly (all belong to Student Management System)
# Fields: severity, type, title, rule, file, line, risk, status
ISSUES = [
    {
        "id": _uid("issue.sql_injection"),
        "engine_severity": "Critical",
        "issue_type": "Vulnerability",
        "title": "SQL Injection",
        "rule_key": "java:S3649",
        "file_path": "StudentDAO.java",
        "line_number": 42,
        "risk_level": "High",
        "risk_score": 9.1,
        "status": "Open",
        "cwe_id": "CWE-89",
        "owasp_category": "A03:2021",
        "cvss_score": 9.1,
        "description": (
            "User-supplied data is concatenated directly into a SQL query string "
            "at line 42. An attacker can craft input that alters the intended query "
            "logic, potentially exposing all student records or allowing unauthorised "
            "data modification."
        ),
        "ai_explanation": (
            "The vulnerability arises because the query is assembled by string "
            "concatenation before being sent to the database. The database engine "
            "has no way to distinguish between the intended SQL structure and injected "
            "input — the entire string is parsed as SQL.\n\n"
            "For example, if an attacker provides ' OR '1'='1, the resulting query "
            "returns all student records regardless of the intended filter."
        ),
    },
    {
        "id": _uid("issue.hardcoded_password"),
        "engine_severity": "Critical",
        "issue_type": "Vulnerability",
        "title": "Hard-coded Password",
        "rule_key": "java:S2068",
        "file_path": "DatabaseConfig.java",
        "line_number": 15,
        "risk_level": "High",
        "risk_score": 8.5,
        "status": "Open",
        "cwe_id": "CWE-259",
        "owasp_category": "A02:2021",
        "cvss_score": 8.5,
        "description": (
            "A password is hard-coded as a string literal at line 15 of "
            "DatabaseConfig.java. If the source code is ever exposed, the credential "
            "is immediately compromised."
        ),
        "ai_explanation": None,
    },
    {
        "id": _uid("issue.null_pointer"),
        "engine_severity": "High",
        "issue_type": "Bug",
        "title": "Null Pointer Dereference",
        "rule_key": "java:S2259",
        "file_path": "StudentService.java",
        "line_number": 87,
        "risk_level": "High",
        "risk_score": 7.2,
        "status": "Open",
        "cwe_id": "CWE-476",
        "owasp_category": None,
        "cvss_score": None,
        "description": (
            "The value of a potentially null reference is used without a null check "
            "at line 87. This can cause a NullPointerException at runtime."
        ),
        "ai_explanation": None,
    },
    {
        "id": _uid("issue.resource_leak"),
        "engine_severity": "High",
        "issue_type": "Bug",
        "title": "Resource Leak",
        "rule_key": "java:S2093",
        "file_path": "ReportGenerator.java",
        "line_number": 134,
        "risk_level": "Medium",
        "risk_score": 5.5,
        "status": "In Review",
        "cwe_id": "CWE-772",
        "owasp_category": None,
        "cvss_score": None,
        "description": (
            "A Closeable resource opened at line 134 is not guaranteed to be closed. "
            "Over time this can exhaust file descriptors or database connections."
        ),
        "ai_explanation": None,
    },
    {
        "id": _uid("issue.cognitive_complexity"),
        "engine_severity": "Medium",
        "issue_type": "Code Smell",
        "title": "High Cognitive Complexity",
        "rule_key": "java:S3776",
        "file_path": "EnrollmentManager.java",
        "line_number": 201,
        "risk_level": "Low",
        "risk_score": 3.0,
        "status": "Open",
        "cwe_id": None,
        "owasp_category": None,
        "cvss_score": None,
        "description": (
            "The method at line 201 has a cognitive complexity score above the "
            "configured threshold. High complexity makes code harder to understand, "
            "test and maintain."
        ),
        "ai_explanation": None,
    },
    {
        "id": _uid("issue.duplicate_code"),
        "engine_severity": "Medium",
        "issue_type": "Code Smell",
        "title": "Duplicate Code",
        "rule_key": "java:S1192",
        "file_path": "GradeCalculator.java",
        "line_number": 56,
        "risk_level": "Low",
        "risk_score": 2.5,
        "status": "Open",
        "cwe_id": None,
        "owasp_category": None,
        "cvss_score": None,
        "description": (
            "A string literal is repeated multiple times. Centralising it in a "
            "constant reduces the risk of inconsistent changes."
        ),
        "ai_explanation": None,
    },
    {
        "id": _uid("issue.unused_variable"),
        "engine_severity": "Low",
        "issue_type": "Code Smell",
        "title": "Unused Variable",
        "rule_key": "java:S1481",
        "file_path": "CourseController.java",
        "line_number": 23,
        "risk_level": "Low",
        "risk_score": 1.0,
        "status": "Open",
        "cwe_id": None,
        "owasp_category": None,
        "cvss_score": None,
        "description": (
            "A local variable declared at line 23 is never read after assignment. "
            "Remove it to reduce noise."
        ),
        "ai_explanation": None,
    },
    {
        "id": _uid("issue.weak_crypto"),
        "engine_severity": "High",
        "issue_type": "Security Hotspot",
        "title": "Weak Cryptography Algorithm",
        "rule_key": "java:S4426",
        "file_path": "AuthService.java",
        "line_number": 67,
        "risk_level": "High",
        "risk_score": 7.8,
        "status": "Open",
        "cwe_id": "CWE-326",
        "owasp_category": "A02:2021",
        "cvss_score": None,
        "description": (
            "A cryptographic algorithm that is considered weak or broken is used at "
            "line 67. Replace it with a currently recommended algorithm."
        ),
        "ai_explanation": None,
    },
]

# Learning resources — matches Learning.tsx
LEARNING_RESOURCES = [
    {
        "id": _uid("lr.sql_injection"),
        "title": "Understanding SQL Injection",
        "resource_type": "Article",
        "duration_minutes": 8,
        "description": (
            "A plain-language explanation of how SQL injection attacks work and why "
            "they are dangerous."
        ),
        "tag": "Security",
        "is_curated": True,
        "related_issue_type": "Vulnerability",
        "related_rule_key": "java:S3649",
    },
    {
        "id": _uid("lr.secure_db_queries"),
        "title": "Secure Database Queries in Java",
        "resource_type": "Tutorial",
        "duration_minutes": 12,
        "description": (
            "How to use PreparedStatements and parameterised queries to prevent "
            "injection."
        ),
        "tag": "Security",
        "is_curated": True,
        "related_issue_type": "Vulnerability",
        "related_rule_key": "java:S3649",
    },
    {
        "id": _uid("lr.input_validation"),
        "title": "Input Validation Best Practices",
        "resource_type": "Guide",
        "duration_minutes": 10,
        "description": (
            "Techniques for validating and sanitising user-supplied data at system "
            "boundaries."
        ),
        "tag": "Security",
        "is_curated": True,
        "related_issue_type": "Vulnerability",
        "related_rule_key": None,
    },
    {
        "id": _uid("lr.owasp_top10"),
        "title": "OWASP Top 10: Injection Attacks (A03:2021)",
        "resource_type": "Guide",
        "duration_minutes": 15,
        "description": None,
        "tag": "Security",
        "is_curated": True,
        "related_issue_type": None,
        "related_rule_key": None,
    },
    {
        "id": _uid("lr.code_smells"),
        "title": "Understanding Code Smells",
        "resource_type": "Article",
        "duration_minutes": 10,
        "description": None,
        "tag": "Quality",
        "is_curated": True,
        "related_issue_type": "Code Smell",
        "related_rule_key": None,
    },
    {
        "id": _uid("lr.technical_debt"),
        "title": "Technical Debt Basics",
        "resource_type": "Article",
        "duration_minutes": 6,
        "description": None,
        "tag": "Quality",
        "is_curated": True,
        "related_issue_type": None,
        "related_rule_key": None,
    },
    {
        "id": _uid("lr.secure_coding_java"),
        "title": "Secure Coding Practices in Java",
        "resource_type": "Tutorial",
        "duration_minutes": 25,
        "description": None,
        "tag": "Security",
        "is_curated": True,
        "related_issue_type": None,
        "related_rule_key": None,
    },
]

LEARNING_PATHS = [
    {
        "id": _uid("lp.secure_java"),
        "name": "Secure Java Development",
        "description": "Secure coding patterns for Java applications",
        "module_count": 6,
    },
    {
        "id": _uid("lp.code_quality"),
        "name": "Code Quality Fundamentals",
        "description": "Understanding and reducing technical debt",
        "module_count": 4,
    },
    {
        "id": _uid("lp.owasp_essentials"),
        "name": "OWASP Security Essentials",
        "description": "Cover the OWASP Top 10 vulnerability classes",
        "module_count": 10,
    },
]


async def seed(session: AsyncSession) -> None:
    now = datetime.now(tz=timezone.utc)

    # ── 1. User ────────────────────────────────────────────────────────────────
    await session.execute(
        pg_insert(User.__table__)
        .values(
            id=USER_ID,
            email=USER_EMAIL,
            password_hash=hash_password("password"),
            full_name="Jane Doe",
            system_role="member",
            department="Computer Science",
            experience_level="intermediate",
            is_email_verified=True,
            is_active=True,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )

    # ── 2. Projects + memberships + analysis jobs ──────────────────────────────
    sms_job_id: uuid.UUID | None = None

    for p in PROJECTS:
        completed_at = now - timedelta(hours=p["offset_hours"])
        project_id = p["id"]
        job_id = _uid(f"job.{p['name']}")

        await session.execute(
            pg_insert(Project.__table__)
            .values(
                id=project_id,
                name=p["name"],
                default_branch=p["branch"],
                owner_id=USER_ID,
                source_type=None,
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )

        await session.execute(
            pg_insert(ProjectMembership.__table__)
            .values(project_id=project_id, user_id=USER_ID, role="owner")
            .on_conflict_do_nothing(index_elements=["project_id", "user_id"])
        )

        await session.execute(
            pg_insert(AnalysisJob.__table__)
            .values(
                id=job_id,
                project_id=project_id,
                status="completed",
                source_branch=p["branch"],
                quality_gate_passed=p["quality_gate_passed"],
                bugs_count=p["bugs"],
                vulnerabilities_count=p["vulnerabilities"],
                code_smells_count=p["code_smells"],
                security_hotspots_count=p["security_hotspots"],
                coverage_pct=p["coverage_pct"],
                duplications_pct=p["duplications_pct"],
                technical_debt_minutes=p["technical_debt_minutes"],
                completed_at=completed_at,
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )

        if p["name"] == "Student Management System":
            sms_job_id = job_id

    # ── 3. Issues (all belong to SMS) ─────────────────────────────────────────
    sms_project_id = _uid("project.sms")
    if sms_job_id is not None:
        for issue in ISSUES:
            await session.execute(
                pg_insert(Finding.__table__)
                .values(
                    id=issue["id"],
                    analysis_job_id=sms_job_id,
                    project_id=sms_project_id,
                    engine_severity=issue["engine_severity"],
                    risk_level=issue["risk_level"],
                    risk_score=issue["risk_score"],
                    risk_score_version="v1.0",
                    issue_type=issue["issue_type"],
                    title=issue["title"],
                    rule_key=issue["rule_key"],
                    file_path=issue["file_path"],
                    line_number=issue["line_number"],
                    status=issue["status"],
                    description=issue["description"],
                    ai_explanation=issue["ai_explanation"],
                    cwe_id=issue["cwe_id"],
                    owasp_category=issue["owasp_category"],
                    cvss_score=issue["cvss_score"],
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )

    # ── 4. Learning resources ──────────────────────────────────────────────────
    for lr in LEARNING_RESOURCES:
        await session.execute(
            pg_insert(LearningResource.__table__)
            .values(**lr)
            .on_conflict_do_nothing(index_elements=["id"])
        )

    # ── 5. Learning paths ──────────────────────────────────────────────────────
    for lp in LEARNING_PATHS:
        await session.execute(
            pg_insert(LearningPath.__table__)
            .values(**lp)
            .on_conflict_do_nothing(index_elements=["id"])
        )

    # ── 6. Path-resource associations ─────────────────────────────────────────
    #
    # Secure Java Development (4 linked resources):
    #   sql_injection, secure_db_queries, input_validation, secure_coding_java
    # Code Quality Fundamentals (2 linked resources):
    #   code_smells, technical_debt
    # OWASP Security Essentials (3 linked resources):
    #   owasp_top10, input_validation, secure_coding_java
    #
    # Resources may belong to multiple paths.
    path_resource_rows = [
        # Secure Java Development
        {"id": _uid("lpr.sj.sql"),        "path_id": _uid("lp.secure_java"),       "resource_id": _uid("lr.sql_injection"),       "position": 1},
        {"id": _uid("lpr.sj.db"),         "path_id": _uid("lp.secure_java"),       "resource_id": _uid("lr.secure_db_queries"),   "position": 2},
        {"id": _uid("lpr.sj.input"),      "path_id": _uid("lp.secure_java"),       "resource_id": _uid("lr.input_validation"),    "position": 3},
        {"id": _uid("lpr.sj.secure"),     "path_id": _uid("lp.secure_java"),       "resource_id": _uid("lr.secure_coding_java"),  "position": 4},
        # Code Quality Fundamentals
        {"id": _uid("lpr.cq.smells"),     "path_id": _uid("lp.code_quality"),      "resource_id": _uid("lr.code_smells"),         "position": 1},
        {"id": _uid("lpr.cq.debt"),       "path_id": _uid("lp.code_quality"),      "resource_id": _uid("lr.technical_debt"),      "position": 2},
        # OWASP Security Essentials
        {"id": _uid("lpr.ow.owasp"),      "path_id": _uid("lp.owasp_essentials"),  "resource_id": _uid("lr.owasp_top10"),         "position": 1},
        {"id": _uid("lpr.ow.input"),      "path_id": _uid("lp.owasp_essentials"),  "resource_id": _uid("lr.input_validation"),    "position": 2},
        {"id": _uid("lpr.ow.secure"),     "path_id": _uid("lp.owasp_essentials"),  "resource_id": _uid("lr.secure_coding_java"),  "position": 3},
    ]
    for row in path_resource_rows:
        await session.execute(
            pg_insert(LearningPathResource.__table__)
            .values(**row)
            .on_conflict_do_nothing(index_elements=["id"])
        )

    # ── 7. Sample resource completions for Jane Doe ────────────────────────────
    #
    # Completing lr.sql_injection and lr.secure_db_queries gives Secure Java Dev
    # 2/4 = 50% progress; completing lr.owasp_top10 gives OWASP Essentials 1/3 ≈ 33%.
    resource_completion_records = [
        {
            "id": _uid("progress.lr.sql_injection"),
            "user_id": USER_ID,
            "path_id": None,
            "resource_id": _uid("lr.sql_injection"),
            "progress_pct": 1.0,
            "completed_at": now - timedelta(hours=48),
        },
        {
            "id": _uid("progress.lr.secure_db_queries"),
            "user_id": USER_ID,
            "path_id": None,
            "resource_id": _uid("lr.secure_db_queries"),
            "progress_pct": 1.0,
            "completed_at": now - timedelta(hours=24),
        },
        {
            "id": _uid("progress.lr.owasp_top10"),
            "user_id": USER_ID,
            "path_id": None,
            "resource_id": _uid("lr.owasp_top10"),
            "progress_pct": 1.0,
            "completed_at": now - timedelta(hours=12),
        },
    ]
    for pr in resource_completion_records:
        await session.execute(
            pg_insert(UserLearningProgress.__table__)
            .values(**pr)
            .on_conflict_do_nothing(index_elements=["id"])
        )

    await session.commit()
    print("Seed complete.")
    print(f"  User:       {USER_EMAIL}  /  password")
    print(f"  Projects:   {len(PROJECTS)}")
    print(f"  Issues:     {len(ISSUES)}  (Student Management System)")
    print(f"  Resources:  {len(LEARNING_RESOURCES)}")
    print(f"  Paths:      {len(LEARNING_PATHS)}")
    print(f"  Path-resource links: {len(path_resource_rows)}")
    print(f"  Completed resources: {len(resource_completion_records)}")


async def main() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
