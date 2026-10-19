import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.database import get_db
from app.models.project import Project, ProjectMembership
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)

DbDep = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """Validate JWT bearer token and return the active user."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not credentials:
        raise unauthorized
    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str = payload.get("sub", "")
        if not user_id:
            raise unauthorized
    except jwt.InvalidTokenError:
        raise unauthorized

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id), User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_project_membership(
    project_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
    min_role: str = "viewer",
) -> tuple[Project, str]:
    """
    Return (project, membership_role) if the current user is a member.
    Raises 404 for non-existent or archived projects.
    Raises 403 if the user has no membership.

    Roles in ascending access order: viewer < developer < owner.
    System administrators have implicit owner-level access to all projects.
    """
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.archived_at.is_(None),
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # System admins bypass membership check
    if current_user.system_role == "system_admin":
        return project, "owner"

    membership_result = await db.execute(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == current_user.id,
        )
    )
    membership = membership_result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    _role_rank = {"viewer": 0, "developer": 1, "owner": 2}
    if _role_rank.get(membership.role, 0) < _role_rank.get(min_role, 0):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    return project, membership.role
