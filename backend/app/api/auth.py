from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.config import settings
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    UserPreferences,
    UserPublic,
    _VALID_AI_LEVELS,
    _VALID_AUTO_RUN,
    _VALID_EMAIL_NOTIFS,
    _VALID_ISSUE_SORTS,
)


class PreferencesUpdate(BaseModel):
    email_notifications: str | None = None
    default_issue_sort: str | None = None
    ai_explain_level: str | None = None
    default_branch: str | None = None
    auto_run_analysis: str | None = None
    analysis_exclusions: str | None = None
    quality_gate_max_bugs: int | None = None
    quality_gate_max_vulnerabilities: int | None = None
    quality_gate_max_code_smells: int | None = None
    quality_gate_coverage_threshold: float | None = None
    quality_gate_debt_hours: int | None = None


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    department: str | None = None
    experience_level: str | None = None  # beginner | intermediate | advanced
    preferences: PreferencesUpdate | None = None

    model_config = {"str_strip_whitespace": True}


_VALID_EXPERIENCE_LEVELS = {"beginner", "intermediate", "advanced"}

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(body: LoginRequest, db: DbDep) -> LoginResponse:
    """
    Authenticate with email and password.
    Returns a JWT access token and the authenticated user's public profile.
    Password hash is never included in any response.
    """
    result = await db.execute(
        select(User).where(User.email == body.email.lower(), User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()

    # Use a constant-time comparison via verify_password even when user is not found
    # to avoid timing-based enumeration.
    dummy_hash = "$2b$12$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    hash_to_check = user.password_hash if user else dummy_hash
    password_ok = verify_password(body.password, hash_to_check)

    if user is None or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(subject=str(user.id))
    expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserPublic.model_validate(user),
    )


@router.get("/me", response_model=UserPublic)
async def me(current_user: CurrentUser) -> UserPublic:
    """Return the authenticated user's profile."""
    return UserPublic.model_validate(current_user)


@router.patch("/me", response_model=UserPublic)
async def update_me(body: ProfileUpdate, current_user: CurrentUser, db: DbDep) -> UserPublic:
    """Update the current user's editable profile fields."""
    if body.full_name is not None:
        if not body.full_name:
            raise HTTPException(status_code=422, detail="full_name cannot be empty")
        current_user.full_name = body.full_name
    if body.department is not None:
        current_user.department = body.department or None
    if body.experience_level is not None:
        if body.experience_level not in _VALID_EXPERIENCE_LEVELS:
            raise HTTPException(
                status_code=422,
                detail=f"experience_level must be one of {sorted(_VALID_EXPERIENCE_LEVELS)}",
            )
        current_user.experience_level = body.experience_level

    if body.preferences is not None:
        p = body.preferences
        # Load and merge into existing preferences (never overwrite with None)
        existing = UserPreferences.model_validate(current_user.preferences or {})

        if p.email_notifications is not None:
            if p.email_notifications not in _VALID_EMAIL_NOTIFS:
                raise HTTPException(status_code=422, detail=f"email_notifications must be one of {sorted(_VALID_EMAIL_NOTIFS)}")
            existing.email_notifications = p.email_notifications

        if p.default_issue_sort is not None:
            if p.default_issue_sort not in _VALID_ISSUE_SORTS:
                raise HTTPException(status_code=422, detail=f"default_issue_sort must be one of {sorted(_VALID_ISSUE_SORTS)}")
            existing.default_issue_sort = p.default_issue_sort

        if p.ai_explain_level is not None:
            if p.ai_explain_level not in _VALID_AI_LEVELS:
                raise HTTPException(status_code=422, detail=f"ai_explain_level must be one of {sorted(_VALID_AI_LEVELS)}")
            existing.ai_explain_level = p.ai_explain_level

        if p.default_branch is not None:
            branch = p.default_branch.strip()
            if not branch or len(branch) > 255:
                raise HTTPException(status_code=422, detail="default_branch must be 1–255 characters")
            existing.default_branch = branch

        if p.auto_run_analysis is not None:
            if p.auto_run_analysis not in _VALID_AUTO_RUN:
                raise HTTPException(status_code=422, detail=f"auto_run_analysis must be one of {sorted(_VALID_AUTO_RUN)}")
            existing.auto_run_analysis = p.auto_run_analysis

        if p.analysis_exclusions is not None:
            if len(p.analysis_exclusions) > 2000:
                raise HTTPException(status_code=422, detail="analysis_exclusions too long (max 2000 chars)")
            existing.analysis_exclusions = p.analysis_exclusions

        if p.quality_gate_max_bugs is not None:
            if not (0 <= p.quality_gate_max_bugs <= 100):
                raise HTTPException(status_code=422, detail="quality_gate_max_bugs must be 0–100")
            existing.quality_gate_max_bugs = p.quality_gate_max_bugs

        if p.quality_gate_max_vulnerabilities is not None:
            if not (0 <= p.quality_gate_max_vulnerabilities <= 100):
                raise HTTPException(status_code=422, detail="quality_gate_max_vulnerabilities must be 0–100")
            existing.quality_gate_max_vulnerabilities = p.quality_gate_max_vulnerabilities

        if p.quality_gate_max_code_smells is not None:
            if not (0 <= p.quality_gate_max_code_smells <= 1000):
                raise HTTPException(status_code=422, detail="quality_gate_max_code_smells must be 0–1000")
            existing.quality_gate_max_code_smells = p.quality_gate_max_code_smells

        if p.quality_gate_coverage_threshold is not None:
            if not (0.0 <= p.quality_gate_coverage_threshold <= 100.0):
                raise HTTPException(status_code=422, detail="quality_gate_coverage_threshold must be 0–100")
            existing.quality_gate_coverage_threshold = p.quality_gate_coverage_threshold

        if p.quality_gate_debt_hours is not None:
            if not (0 <= p.quality_gate_debt_hours <= 9999):
                raise HTTPException(status_code=422, detail="quality_gate_debt_hours must be 0–9999")
            existing.quality_gate_debt_hours = p.quality_gate_debt_hours

        current_user.preferences = existing.model_dump()

    db.add(current_user)
    await db.flush()
    return UserPublic.model_validate(current_user)
