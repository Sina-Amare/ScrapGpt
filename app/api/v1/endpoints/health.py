"""
Health check endpoints.

These endpoints are used by:
- Load balancers for health checks
- Kubernetes liveness/readiness probes
- Monitoring systems

Health check endpoints should be fast and not require authentication.
"""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings


router = APIRouter(tags=["Health"])


# -----------------------------------------------------------------------------
# Response Schemas
# -----------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str
    environment: str
    version: str


class HealthDetailResponse(BaseModel):
    """Detailed health check response with component status."""
    status: str
    environment: str
    version: str
    database: str
    

# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Basic health check",
    description="Returns the basic health status of the API. Use this for simple uptime monitoring.",
)
async def health_check() -> HealthResponse:
    """
    Basic health check endpoint.
    
    This endpoint is intentionally simple and fast.
    It doesn't check database connectivity - use /health/ready for that.
    
    Returns:
        HealthResponse: Status information
    """
    return HealthResponse(
        status="healthy",
        environment=settings.ENVIRONMENT,
        version="0.1.0",
    )


@router.get(
    "/health/ready",
    response_model=HealthDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness check with dependencies",
    description="Checks if the API and all its dependencies (database, etc.) are ready to serve traffic.",
)
async def readiness_check(
    db: AsyncSession = Depends(get_db),
) -> HealthDetailResponse:
    """
    Readiness check endpoint.
    
    This endpoint verifies that:
    - The API is running
    - Database is connected and responding
    
    Use this for Kubernetes readiness probes or load balancer health checks.
    
    Args:
        db: Database session (injected)
        
    Returns:
        HealthDetailResponse: Detailed status of all components
    """
    # Check database connectivity
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return HealthDetailResponse(
        status="healthy" if db_status == "connected" else "degraded",
        environment=settings.ENVIRONMENT,
        version="0.1.0",
        database=db_status,
    )


@router.get(
    "/health/live",
    status_code=status.HTTP_200_OK,
    summary="Liveness check",
    description="Simple liveness probe. Returns 200 if the process is alive.",
)
async def liveness_check() -> dict:
    """
    Liveness check endpoint.
    
    This is the simplest possible health check.
    If this returns, the process is alive.
    
    Use this for Kubernetes liveness probes.
    
    Returns:
        dict: Simple alive status
    """
    return {"alive": True}
