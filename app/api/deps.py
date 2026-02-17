"""
API dependency injection functions.

This module provides reusable dependencies for FastAPI route handlers:
- Database session management
- Authentication/authorization
- Credit checking for scraping
- Common query parameters

Usage:
    from app.api.deps import get_db, get_current_user, require_credits

    @router.get("/me")
    async def get_me(
        current_user: User = Depends(get_current_user),
    ):
        return current_user
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
__all__ = ["get_db", "get_current_user", "get_optional_user", "require_credits"]


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
    user_id = int(payload.sub)
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

    user_id = int(payload.sub)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    return user


async def require_credits(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    DEPRECATED: Use admission.py credit check instead.

    This dependency uses the old lazy reset policy.
    Credits now reset at 00:00 UTC via scheduler.

    Raises:
        HTTPException: 403 if no credits available
    """
    import warnings
    warnings.warn(
        "require_credits is deprecated. Use admission.py credit check.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Check credits (no lazy reset - scheduler handles reset now)
    if current_user.credits_remaining <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": "No credits remaining",
                "error_type": "INSUFFICIENT_CREDITS",
            },
        )

    return current_user


async def deduct_credit(
    user: User,
    db: AsyncSession,
) -> None:
    """
    DEPRECATED: Credits are now deducted atomically in task_state.py.

    Do not use this function - it's not atomic and can cause race conditions.
    """
    import warnings
    warnings.warn(
        "deduct_credit is deprecated. Use task_state.transition_to_llm_processing.",
        DeprecationWarning,
        stacklevel=2,
    )
    user.credits_remaining -= 1
    await db.commit()


# -----------------------------------------------------------------------------
# Type Aliases for Clean Dependency Injection
# -----------------------------------------------------------------------------

CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[Optional[User], Depends(get_optional_user)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
UserWithCredits = Annotated[User, Depends(require_credits)]


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

