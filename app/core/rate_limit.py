"""
Rate limiting configuration for ScrapGPT.

Implements per-user rate limiting to prevent abuse.
Uses slowapi (production-ready, based on flask-limiter).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

from app.core.config import settings


def get_user_identifier(request: Request) -> str:
    """
    Get rate limit key from request.

    Priority:
    1. Authenticated user ID (from JWT)
    2. IP address (for unauthenticated requests)
    """
    # Try to get user from request state (set by auth dependency)
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "id"):
        return f"user:{user.id}"

    # Fall back to IP address
    return get_remote_address(request)


# Global limiter instance
limiter = Limiter(
    key_func=get_user_identifier,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
    storage_uri="memory://",  # In-memory for single instance
)


# Rate limit decorators for specific endpoints
SCRAPE_RATE_LIMIT = f"{settings.RATE_LIMIT_SCRAPE_PER_MINUTE}/minute"
AUTH_RATE_LIMIT = f"{settings.RATE_LIMIT_AUTH_PER_MINUTE}/minute"
