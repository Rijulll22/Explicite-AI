import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class LearningResourceOut(BaseModel):
    id: uuid.UUID
    title: str
    resource_type: str
    duration_minutes: int | None
    description: str | None
    tag: str | None
    related_issue_type: str | None
    related_rule_key: str | None

    model_config = {"from_attributes": True}


class ResourceRecommendation(BaseModel):
    """A learning resource with a relevance explanation and completion flag."""
    id: uuid.UUID
    title: str
    resource_type: str
    duration_minutes: int | None
    description: str | None
    tag: str | None
    related_issue_type: str | None
    related_rule_key: str | None
    match_reason: str
    is_completed: bool

    model_config = {"from_attributes": False}


class LearningPathOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    module_count: int
    progress_pct: float

    model_config = {"from_attributes": True}


class LearningProgressStats(BaseModel):
    resources_completed: int
    resources_total: int
    tutorials_completed: int
    tutorials_total: int
    paths_started: int
    total_study_minutes: int
    # IDs of resources the user has completed — used by the frontend to
    # pre-populate completion state without a separate request.
    completed_resource_ids: list[uuid.UUID] = []


# ── Tutor session schemas ─────────────────────────────────────────────────────

class TutorStartRequest(BaseModel):
    resource_id: uuid.UUID


class TutorMessageOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TutorSessionOut(BaseModel):
    session_id: uuid.UUID
    resource: LearningResourceOut
    messages: list[TutorMessageOut]

    model_config = {"from_attributes": False}


class TutorChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class TutorChatResponse(BaseModel):
    message: TutorMessageOut
    model_provider: str
    model_name: str
