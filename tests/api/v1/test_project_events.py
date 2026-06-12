"""Endpoint tests for the project activity log (owner-scoping + mapping)."""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI

from app.api import deps
from app.api.v1.endpoints import dashboard, projects
from app.models.job import (
    ExtractionMode,
    Project,
    ProjectState,
    RenderMode,
    WorkflowMode,
)
from app.models.project_event import ProjectEvent
from app.models.user import User


def _user(user_id: int = 1) -> User:
    return User(id=user_id, email="user@test.com", hashed_password="hash")


def _project(user_id: int = 1) -> Project:
    return Project(
        id=1,
        user_id=user_id,
        url="https://example.com/",
        extraction_mode=ExtractionMode.STRUCTURED,
        workflow_mode=WorkflowMode.GUIDED,
        render_mode=RenderMode.AUTO,
        state=ProjectState.COMPLETED,
        warnings=[],
        created_at=datetime.now(timezone.utc),
    )


def _event(event_id: int = 1, project_id: int = 1) -> ProjectEvent:
    event = ProjectEvent(
        id=event_id,
        user_id=1,
        project_id=project_id,
        event_type="extraction.completed",
        level="info",
        message="Extraction completed.",
        created_at=datetime.now(timezone.utc),
    )
    event.event_metadata = {"records": 3}
    return event


class FakeDB:
    def __init__(self, project: Project | None = None):
        self._project = project

    async def get(self, _model, _pk):
        return self._project


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(projects.router, prefix="/api/v1")
    application.include_router(dashboard.router, prefix="/api/v1")
    return application


@pytest.mark.asyncio
async def test_project_events_requires_auth(async_client):
    response = await async_client.get("/api/v1/projects/1/events")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_project_events_are_owner_scoped_404(async_client, app):
    app.dependency_overrides[deps.get_current_user] = lambda: _user(1)
    app.dependency_overrides[deps.get_db] = lambda: (yield FakeDB(project=_project(user_id=2)))

    response = await async_client.get("/api/v1/projects/1/events")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_project_events_returns_mapped_events(async_client, app, monkeypatch):
    app.dependency_overrides[deps.get_current_user] = lambda: _user(1)
    app.dependency_overrides[deps.get_db] = lambda: (yield FakeDB(project=_project(user_id=1)))

    async def fake_list(_db, project_id, user_id, limit=100):
        assert project_id == 1 and user_id == 1
        return [_event()]

    monkeypatch.setattr(projects, "list_project_events", fake_list)

    response = await async_client.get("/api/v1/projects/1/events")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["event_type"] == "extraction.completed"
    # The DB column "metadata" / attribute event_metadata maps to the API field.
    assert body[0]["metadata"] == {"records": 3}


@pytest.mark.asyncio
async def test_dashboard_events_are_user_scoped(async_client, app, monkeypatch):
    app.dependency_overrides[deps.get_current_user] = lambda: _user(7)
    app.dependency_overrides[deps.get_db] = lambda: (yield FakeDB())

    async def fake_list(_db, user_id, limit=100):
        assert user_id == 7
        return [_event(project_id=5)]

    monkeypatch.setattr(dashboard, "list_user_events", fake_list)

    response = await async_client.get("/api/v1/dashboard/events")
    assert response.status_code == 200
    assert response.json()[0]["project_id"] == 5
