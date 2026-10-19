"""
Suggested fix record (SRS FR-FIX-01 – FR-FIX-07).

Lifecycle: proposed → approved | rejected
           approved  → applied  | failed (stale / apply error)

One finding may accumulate multiple proposals; the API returns the latest
non-rejected one by default.  Original source files are NEVER modified
during generation or review — only during an explicit `applied` transition.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from .finding import Finding
    from .project import Project
    from .analysis import AnalysisJob


class SuggestedFix(Base):
    __tablename__ = "suggested_fixes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analysis_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Source reference — used to detect stale fixes (FR-FIX-06)
    # Relative path within the job's source_path directory
    target_file: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # SHA-256 of the full file content at generation time
    original_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Snippet used for context (the lines sent to the model)
    original_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    # First 1-based line number of the snippet
    snippet_start_line: Mapped[int | None] = mapped_column(nullable=True)
    # Last 1-based line number (inclusive)
    snippet_end_line: Mapped[int | None] = mapped_column(nullable=True)

    # AI-proposed replacement for the snippet (same line count as lines, may differ)
    proposed_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Unified diff (computed from original_snippet vs proposed_snippet)
    unified_diff: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI explanation fields
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    caveats: Mapped[str | None] = mapped_column(Text, nullable=True)

    # proposed | approved | rejected | applied | failed | stale
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="proposed", index=True
    )

    # Whether the source file was available during generation
    source_available: Mapped[bool] = mapped_column(nullable=False, default=False)

    # Model metadata
    model_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    finding: Mapped["Finding"] = relationship("Finding")
    project: Mapped["Project"] = relationship("Project")
    analysis_job: Mapped["AnalysisJob"] = relationship("AnalysisJob")
