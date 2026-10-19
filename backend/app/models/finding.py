import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from .analysis import AnalysisJob
    from .project import Project


class Finding(Base):
    """
    Normalised issue record — one row per detected issue in an analysis run.

    engine_severity is the original severity from the analysis engine.
    risk_level and risk_score are Explicite AI's own scoring (SRS FR-RISK-01,
    FR-RISK-03: deterministic, versioned, stored separately).
    """

    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    analysis_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Original engine severity — preserved separately (SRS FR-AN-03)
    # Critical | High | Medium | Low
    engine_severity: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )

    # Explicite AI risk score — separate from engine severity (SRS FR-RISK-01)
    # High | Medium | Low
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Vulnerability | Bug | Code Smell | Security Hotspot
    issue_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    rule_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True, index=True)
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Open | In Review | Resolved
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Open", index=True
    )

    # Security metadata
    cwe_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    owasp_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cvss_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    cvss_vector: Mapped[str | None] = mapped_column(String(300), nullable=True)
    cvss_version: Mapped[str | None] = mapped_column(String(10), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    analysis_job: Mapped["AnalysisJob"] = relationship(
        "AnalysisJob", back_populates="findings"
    )
    project: Mapped["Project"] = relationship("Project")
