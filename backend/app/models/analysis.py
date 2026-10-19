import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from .project import Project
    from .finding import Finding


class AnalysisJob(Base):
    """
    Represents a single analysis run for a project revision.

    The engine fields are nullable so the record can be created before the
    adapter has been selected and before the job actually runs.
    status transitions: queued → running → completed | failed | cancelled
    """

    __tablename__ = "analysis_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # queued | running | completed | failed | cancelled
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="queued", index=True
    )
    source_revision: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    engine_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    engine_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    scoring_model_version: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    # Aggregated metrics — populated when status = completed
    quality_gate_passed: Mapped[bool | None] = mapped_column(nullable=True)
    bugs_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vulnerabilities_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    code_smells_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    security_hotspots_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    coverage_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    duplications_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    technical_debt_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Internal path to extracted source — never exposed in API responses
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    project: Mapped["Project"] = relationship("Project", back_populates="analysis_jobs")
    findings: Mapped[list["Finding"]] = relationship(
        "Finding", back_populates="analysis_job", cascade="all, delete-orphan"
    )
