"""
API dependency injection functions.

This module provides reusable dependencies for FastAPI route handlers:
- Database session management
- Authentication/authorization
- Common query parameters

Usage:
    from app.api.deps import get_db, get_current_user
    
    @router.get("/me")
    async def get_me(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        return current_user
"""

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import verify_token, TokenPayload
from app.db.database import get_db

# Re-export get_db for convenience
__all__ = ["get_db", "get_current_user", "get_optional_user"]


# -----------------------------------------------------------------------------
# OAuth2 Configuration
# -----------------------------------------------------------------------------

# OAuth2 password bearer flow
# tokenUrl must match your login endpoint
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login",
    auto_error=True,
)

# Optional version that doesn't raise on missing token
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
) -> dict:
    """
    Dependency that extracts and validates the current user from JWT token.
    
    This dependency:
    1. Extracts the JWT token from the Authorization header
    2. Validates the token signature and expiration
    3. Returns the user data (extend to fetch full user from DB)
    
    Args:
        token: JWT token from Authorization header
        db: Database session (for user lookup)
        
    Returns:
        dict: User information from the token
        
    Raises:
        HTTPException: 401 if token is invalid or expired
        
    Usage:
        @router.get("/protected")
        async def protected_route(user: dict = Depends(get_current_user)):
            return {"user": user}
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = verify_token(token, token_type="access")
    
    if payload is None:
        raise credentials_exception
    
    # TODO: Fetch full user from database using payload.sub
    # For now, return the token payload as user info
    # Example:
    # user = await db.execute(select(User).where(User.id == int(payload.sub)))
    # user = user.scalar_one_or_none()
    # if user is None:
    #     raise credentials_exception
    
    return {
        "id": payload.sub,
        "token_type": payload.type,
    }


async def get_optional_user(
    token: Annotated[Optional[str], Depends(oauth2_scheme_optional)],
    db: AsyncSession = Depends(get_db),
) -> Optional[dict]:
    """
    Dependency that optionally extracts user from JWT token.
    
    Unlike get_current_user, this doesn't raise an error if no token
    is provided. Useful for routes that behave differently for
    authenticated vs anonymous users.
    
    Args:
        token: Optional JWT token from Authorization header
        db: Database session
        
    Returns:
        dict | None: User information if authenticated, None otherwise
        
    Usage:
        @router.get("/items")
        async def get_items(user: Optional[dict] = Depends(get_optional_user)):
            if user:
                return {"items": user_specific_items}
            return {"items": public_items}
    """
    if token is None:
        return None
    
    payload = verify_token(token, token_type="access")
    
    if payload is None:
        return None
    
    return {
        "id": payload.sub,
        "token_type": payload.type,
    }


# -----------------------------------------------------------------------------
# Type Aliases for Clean Dependency Injection
# -----------------------------------------------------------------------------

# Use these in route handlers for cleaner signatures
CurrentUser = Annotated[dict, Depends(get_current_user)]
OptionalUser = Annotated[Optional[dict], Depends(get_optional_user)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


# -----------------------------------------------------------------------------
# Common Query Parameters
# -----------------------------------------------------------------------------

class PaginationParams:
    """
    Common pagination parameters dependency.
    
    Usage:
        @router.get("/items")
        async def get_items(pagination: PaginationParams = Depends()):
            skip = pagination.skip
            limit = pagination.limit
    """
    
    def __init__(
        self,
        skip: int = 0,
        limit: int = 100,
    ):
        self.skip = max(0, skip)  # Ensure non-negative
        self.limit = min(limit, 100)  # Cap at 100
