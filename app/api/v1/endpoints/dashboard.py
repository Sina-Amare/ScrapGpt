"""Dashboard aggregate endpoints (cross-project views)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.project import ProjectEventResponse
from app.services.project_events import list_user_events

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/events",
    response_model=list[ProjectEventResponse],
    summary="Recent activity across all of the user's projects",
)
async def dashboard_events(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ProjectEventResponse]:
    events = await list_user_events(db, user.id, limit=limit)
    return [ProjectEventResponse.from_event(event) for event in events]
