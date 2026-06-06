"""
Tests for GET /scrape/tasks (list) and GET /scrape/tasks/{id}.

Covers: pagination params, user isolation, ordering, content_length population,
and the 404 path for cross-user access.
"""

from datetime import datetime, timezone, timedelta

import pytest
from fastapi import FastAPI

from app.api import deps
from app.api.v1.endpoints import scrape
from app.models.scrape_task import ScrapeTask, TaskState
from app.models.user import User


# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------


def _task(
    task_id: int = 1,
    user_id: int = 1,
    state: TaskState = TaskState.COMPLETED,
    url: str = "https://example.com",
    error: str | None = None,
    result: dict | None = None,
    content: str | None = "scraped text",
    offset_seconds: int = 0,
) -> ScrapeTask:
    return ScrapeTask(
        id=task_id,
        user_id=user_id,
        state=state,
        url=url,
        error=error,
        result=result,
        content=content,
        created_at=datetime.now(timezone.utc) - timedelta(seconds=offset_seconds),
    )


class FakeScalarsResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class FakeListResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return FakeScalarsResult(self._items)

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


class FakeListSession:
    def __init__(self, tasks: list[ScrapeTask]):
        self._tasks = tasks
        self.last_statement = None

    async def execute(self, statement):
        self.last_statement = statement
        return FakeListResult(self._tasks)

    async def get(self, model, pk):
        for t in self._tasks:
            if t.id == pk:
                return t
        return None

    async def delete(self, obj):
        if obj in self._tasks:
            self._tasks.remove(obj)

    async def commit(self):
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(scrape.router, prefix="/api/v1")
    return application


def _user(user_id: int = 1) -> User:
    return User(id=user_id, email="user@example.com", hashed_password="hash")


# ---------------------------------------------------------------------------
# GET /scrape/tasks — list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tasks_returns_tasks_for_authenticated_user(async_client, app):
    tasks = [_task(task_id=2), _task(task_id=1)]
    session = FakeListSession(tasks)

    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield session)

    response = await async_client.get("/api/v1/scrape/tasks")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["task_id"] == 2
    assert body[1]["task_id"] == 1


@pytest.mark.asyncio
async def test_list_tasks_requires_authentication(async_client, app):
    response = await async_client.get("/api/v1/scrape/tasks")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_tasks_query_uses_user_filter_and_ordering(async_client, app):
    """The SQL statement must filter by user_id, order by created_at DESC, and apply LIMIT."""
    session = FakeListSession([])
    app.dependency_overrides[deps.get_current_user] = lambda: _user(user_id=7)
    app.dependency_overrides[deps.get_db] = lambda: (yield session)

    await async_client.get("/api/v1/scrape/tasks")

    stmt = str(session.last_statement)
    assert "scrape_tasks.user_id" in stmt
    assert "ORDER BY scrape_tasks.created_at DESC" in stmt
    assert "LIMIT" in stmt


@pytest.mark.asyncio
async def test_list_tasks_respects_skip_and_limit_params(async_client, app):
    session = FakeListSession([])
    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield session)

    response = await async_client.get("/api/v1/scrape/tasks?skip=10&limit=5")

    assert response.status_code == 200
    stmt = str(session.last_statement)
    assert "LIMIT" in stmt
    assert "OFFSET" in stmt


@pytest.mark.asyncio
async def test_list_tasks_rejects_invalid_limit(async_client, app):
    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield FakeListSession([]))

    # limit > 100 is rejected
    response = await async_client.get("/api/v1/scrape/tasks?limit=200")
    assert response.status_code == 422

    # negative skip is rejected
    response = await async_client.get("/api/v1/scrape/tasks?skip=-1")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_tasks_does_not_include_content_length(async_client, app):
    """List endpoint defers content — content_length should be absent or null."""
    session = FakeListSession([_task(content="lots of text here")])
    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield session)

    response = await async_client.get("/api/v1/scrape/tasks")

    assert response.status_code == 200
    body = response.json()
    # content_length is not populated on list (deferred content column)
    assert body[0].get("content_length") is None


@pytest.mark.asyncio
async def test_list_tasks_includes_error_on_failed_task(async_client, app):
    failed = _task(state=TaskState.FAILED, error="Scraping timeout after 30s")
    session = FakeListSession([failed])
    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield session)

    response = await async_client.get("/api/v1/scrape/tasks")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["state"] == "FAILED"
    assert body[0]["error"] == "Scraping timeout after 30s"


# ---------------------------------------------------------------------------
# GET /scrape/tasks/{task_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_task_returns_task_with_content_length(async_client, app):
    t = _task(task_id=5, content="x" * 1234)
    session = FakeListSession([t])
    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield session)

    response = await async_client.get("/api/v1/scrape/tasks/5")

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == 5
    assert body["content_length"] == 1234


@pytest.mark.asyncio
async def test_get_task_content_length_is_none_when_not_scraped(async_client, app):
    t = _task(task_id=3, state=TaskState.PERMISSION_GRANTED, content=None)
    session = FakeListSession([t])
    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield session)

    response = await async_client.get("/api/v1/scrape/tasks/3")

    assert response.status_code == 200
    assert response.json()["content_length"] is None


@pytest.mark.asyncio
async def test_get_task_returns_404_for_task_owned_by_another_user(async_client, app):
    # Task belongs to user 2, but request is from user 1
    t = _task(task_id=9, user_id=2)
    session = FakeListSession([t])
    app.dependency_overrides[deps.get_current_user] = lambda: _user(user_id=1)
    app.dependency_overrides[deps.get_db] = lambda: (yield session)

    response = await async_client.get("/api/v1/scrape/tasks/9")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_task_returns_404_when_task_does_not_exist(async_client, app):
    session = FakeListSession([])  # empty — db.get returns None
    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield session)

    response = await async_client.get("/api/v1/scrape/tasks/999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_task_returns_result_on_completed_task(async_client, app):
    result_data = {"summary": "A great page", "key_points": [], "data_type": "article", "word_count": 42}
    t = _task(task_id=10, state=TaskState.COMPLETED, result=result_data)
    session = FakeListSession([t])
    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield session)

    response = await async_client.get("/api/v1/scrape/tasks/10")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "COMPLETED"
    assert body["result"]["summary"] == "A great page"
    assert body["result"]["data_type"] == "article"


# ---------------------------------------------------------------------------
# DELETE /scrape/tasks/{task_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_task_success(async_client, app):
    t = _task(task_id=15, state=TaskState.COMPLETED)
    session = FakeListSession([t])
    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield session)

    response = await async_client.delete("/api/v1/scrape/tasks/15")
    assert response.status_code == 204
    assert len(session._tasks) == 0


@pytest.mark.asyncio
async def test_delete_task_not_found(async_client, app):
    # Trying to delete a task owned by user 2
    t = _task(task_id=16, user_id=2, state=TaskState.COMPLETED)
    session = FakeListSession([t])
    app.dependency_overrides[deps.get_current_user] = lambda: _user(user_id=1)
    app.dependency_overrides[deps.get_db] = lambda: (yield session)

    response = await async_client.delete("/api/v1/scrape/tasks/16")
    assert response.status_code == 404
    assert len(session._tasks) == 1  # Not deleted


@pytest.mark.asyncio
async def test_delete_task_active_fails(async_client, app):
    # Trying to delete a scraping (non-terminal) task
    t = _task(task_id=17, state=TaskState.SCRAPING)
    session = FakeListSession([t])
    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield session)

    response = await async_client.delete("/api/v1/scrape/tasks/17")
    assert response.status_code == 400
    assert len(session._tasks) == 1  # Not deleted

