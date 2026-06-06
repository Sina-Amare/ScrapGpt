import pytest
from fastapi import FastAPI

from app.api import deps
from app.api.v1.endpoints import scrape
from app.models.scrape_task import ScrapeTask, TaskState
from app.models.user import User


class FakeResult:
    def __init__(self, task):
        self.task = task

    def scalar_one_or_none(self):
        return self.task


class FakeSession:
    def __init__(self, task):
        self.task = task
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return FakeResult(self.task)


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(scrape.router, prefix="/api/v1")
    return app


@pytest.mark.asyncio
async def test_current_task_limits_legacy_current_query(async_client, app):
    task = ScrapeTask(
        id=1,
        user_id=1,
        state=TaskState.SCRAPING,
        url="https://example.com",
    )
    session = FakeSession(task)

    async def override_get_current_user():
        return User(id=1, email="user@example.com", hashed_password="hash")

    async def override_get_db():
        yield session

    app.dependency_overrides[deps.get_current_user] = override_get_current_user
    app.dependency_overrides[deps.get_db] = override_get_db

    response = await async_client.get("/api/v1/scrape/tasks/current")

    assert response.status_code == 200
    assert response.json()["task_id"] == 1
    statement = str(session.statement)
    assert "ORDER BY scrape_tasks.created_at DESC" in statement
    assert "LIMIT" in statement
