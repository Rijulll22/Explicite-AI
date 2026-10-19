import uuid
from pydantic import BaseModel, field_validator

_VALID_LEVELS = {"beginner", "intermediate", "advanced"}


class ExplainRequest(BaseModel):
    level: str = "intermediate"
    force: bool = False   # set True to regenerate even if a cached explanation exists

    @field_validator("level")
    @classmethod
    def level_must_be_valid(cls, v: str) -> str:
        if v not in _VALID_LEVELS:
            raise ValueError(f"level must be one of {sorted(_VALID_LEVELS)}")
        return v


class ExplainResponse(BaseModel):
    finding_id: uuid.UUID
    what: str
    why: str
    how_it_arises: str
    remediation: str
    caveats: str
    model_provider: str
    model_name: str
    grounded_in_finding: bool
    source_context_available: bool
    cached: bool


class AssistantRequest(BaseModel):
    message: str
    issue_id: uuid.UUID | None = None

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be empty")
        if len(v) > 1000:
            raise ValueError("message must be 1000 characters or fewer")
        return v


class AssistantResponse(BaseModel):
    reply: str
    model_provider: str
    model_name: str
    grounded: bool
