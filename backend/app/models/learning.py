import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Float, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from .user import User


class LearningResource(Base):
    """Curated or AI-generated learning material (SRS FR-LEARN-01 to FR-LEARN-08)."""

    __tablename__ = "learning_resources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    # Article | Tutorial | Guide
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Security | Quality | etc.
    tag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_curated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Links the resource to a category of issue (e.g. "Vulnerability")
    related_issue_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Related rule key for issue-specific recommendations
    related_rule_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    path_memberships: Mapped[list["LearningPathResource"]] = relationship(
        "LearningPathResource", back_populates="resource", cascade="all, delete-orphan"
    )


class LearningPath(Base):
    """Ordered collection of resources forming a learning track."""

    __tablename__ = "learning_paths"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Planned total module count (curriculum scope); may exceed linked resources
    module_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    progress_records: Mapped[list["UserLearningProgress"]] = relationship(
        "UserLearningProgress",
        back_populates="path",
        cascade="all, delete-orphan",
    )
    path_resources: Mapped[list["LearningPathResource"]] = relationship(
        "LearningPathResource",
        back_populates="path",
        cascade="all, delete-orphan",
        order_by="LearningPathResource.position",
    )


class LearningPathResource(Base):
    """Association between a learning path and its constituent resources.

    A resource may appear in multiple paths. Position controls display order
    within the path. Progress is calculated from this table rather than from
    the stored float in UserLearningProgress.
    """

    __tablename__ = "learning_path_resources"
    __table_args__ = (UniqueConstraint("path_id", "resource_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    path_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_paths.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    path: Mapped["LearningPath"] = relationship("LearningPath", back_populates="path_resources")
    resource: Mapped["LearningResource"] = relationship("LearningResource", back_populates="path_memberships")


class UserLearningProgress(Base):
    """Tracks per-user progress on a learning path or individual resource."""

    __tablename__ = "user_learning_progress"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    path_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_paths.id", ondelete="CASCADE"),
        nullable=True,
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_resources.id", ondelete="CASCADE"),
        nullable=True,
    )
    # 0.0 – 1.0
    progress_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship("User")
    path: Mapped["LearningPath | None"] = relationship(
        "LearningPath", back_populates="progress_records"
    )


class TutorSession(Base):
    """One conversation session per user × learning resource."""

    __tablename__ = "tutor_sessions"
    __table_args__ = (UniqueConstraint("user_id", "resource_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    messages: Mapped[list["TutorMessage"]] = relationship(
        "TutorMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="TutorMessage.created_at",
    )


class TutorMessage(Base):
    """Individual message in a tutor conversation."""

    __tablename__ = "tutor_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tutor_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # "user" | "assistant"
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    session: Mapped["TutorSession"] = relationship("TutorSession", back_populates="messages")
