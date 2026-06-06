"""
API dependency injection functions.

This module provides reusable dependencies for FastAPI route handlers.
"""

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import verify_token
from app.db.database import get_db
from app.models.user import User

# Re-export get_db for convenience
__all__ = ["get_db", "get_current_user", "get_optional_user"]


# -----------------------------------------------------------------------------
# OAuth2 Configuration
# -----------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login",
    auto_error=True,
)

oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login",
    auto_error=False,
)


# -----------------------------------------------------------------------------
# Authentication Dependencies
# -----------------------------------------------------------------------------

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency that extracts and validates the current user from JWT token.

    1. Extracts the JWT token from the Authorization header
    2. Validates the token signature and expiration
    3. Fetches the user from database

    Args:
        token: JWT token from Authorization header
        db: Database session

    Returns:
        User: The authenticated user object

    Raises:
        HTTPException: 401 if token is invalid, expired, or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = verify_token(token, token_type="access")

    if payload is None:
        raise credentials_exception

    # Fetch user from database
    try:
        user_id = int(payload.sub)
    except ValueError:
        raise credentials_exception
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    return user


async def get_optional_user(
    token: Annotated[Optional[str], Depends(oauth2_scheme_optional)],
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Dependency that optionally extracts user from JWT token.

    Unlike get_current_user, this doesn't raise an error if no token
    is provided. Useful for routes that behave differently for
    authenticated vs anonymous users.
    """
    if token is None:
        return None

    payload = verify_token(token, token_type="access")

    if payload is None:
        return None

    try:
        user_id = int(payload.sub)
    except ValueError:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    return user


# -----------------------------------------------------------------------------
# Type Aliases for Clean Dependency Injection
# -----------------------------------------------------------------------------

CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[Optional[User], Depends(get_optional_user)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


# -----------------------------------------------------------------------------
# Common Query Parameters
# -----------------------------------------------------------------------------

class PaginationParams:
    """Common pagination parameters dependency."""

    def __init__(
        self,
        skip: int = 0,
        limit: int = 100,
    ):
        self.skip = max(0, skip)
        self.limit = min(limit, 100)

