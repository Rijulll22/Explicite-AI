import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator

# ── Preference defaults ────────────────────────────────────────────────────────

_VALID_EMAIL_NOTIFS = {"All issues", "Critical and High only", "None"}
_VALID_ISSUE_SORTS = {"Severity (highest first)", "Date detected", "File name"}
_VALID_AI_LEVELS = {"beginner", "intermediate", "advanced"}
_VALID_AUTO_RUN = {"Enabled", "Disabled"}


class UserPreferences(BaseModel):
    """Account-level user preferences stored as JSONB in the users table."""
    # Preferences section
    email_notifications: str = "Critical and High only"
    default_issue_sort: str = "Severity (highest first)"
    ai_explain_level: str = "intermediate"
    # Project Defaults section
    default_branch: str = "main"
    auto_run_analysis: str = "Enabled"
    analysis_exclusions: str = "**/test/**, **/generated/**"
    # Analysis Settings section
    quality_gate_max_bugs: int = Field(default=0, ge=0, le=100)
    quality_gate_max_vulnerabilities: int = Field(default=0, ge=0, le=100)
    quality_gate_max_code_smells: int = Field(default=20, ge=0, le=1000)
    quality_gate_coverage_threshold: float = Field(default=0.0, ge=0.0, le=100.0)
    quality_gate_debt_hours: int = Field(default=24, ge=0, le=9999)

    model_config = {"extra": "ignore"}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("password must not be empty")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserPublic(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    system_role: str
    department: str | None
    experience_level: str
    is_email_verified: bool
    created_at: datetime
    preferences: UserPreferences = Field(default_factory=UserPreferences)

    model_config = {"from_attributes": True}

    @field_validator("preferences", mode="before")
    @classmethod
    def coerce_preferences(cls, v: Any) -> UserPreferences:
        if v is None:
            return UserPreferences()
        if isinstance(v, dict):
            return UserPreferences.model_validate(v)
        return v  # already a UserPreferences instance


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic
