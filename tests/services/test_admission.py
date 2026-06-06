import pytest

from app.core.config import settings
from app.models.scrape_task import ScrapeTask, TaskState
from app.models.user import User
from app.services.admission import (
    AdmissionError,
    AdmissionErrorType,
    AdmissionSuccess,
    admit_scrape_task,
)


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value

    def scalar_one_or_none(self):
        return self.value


class FakeSession:
    def __init__(self, results):
        self.results = list(results)
        self.statements = []
        self.added = None
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0
        self.refreshes = 0

    async def execute(self, statement, _params=None):
        self.statements.append(str(statement))
        return self.results.pop(0)

    def add(self, item):
        self.added = item
        item.id = 123

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, _item):
        self.refreshes += 1


def _user() -> User:
    return User(id=1, email="user@example.com", hashed_password="hash")


@pytest.mark.asyncio
async def test_admit_scrape_task_creates_task_without_credit_fields(monkeypatch):
    monkeypatch.setattr(settings, "MAX_CONCURRENT_JOBS_PER_USER", 3)
    db = FakeSession([FakeResult(None), FakeResult(0)])

    result = await admit_scrape_task(_user(), "https://example.com", db)

    assert isinstance(result, AdmissionSuccess)
    assert isinstance(db.added, ScrapeTask)
    assert db.added.state == TaskState.PERMISSION_GRANTED
    assert db.commits == 1
    assert db.rollbacks == 0
    assert any("pg_advisory_xact_lock" in statement for statement in db.statements)


@pytest.mark.asyncio
async def test_admit_scrape_task_blocks_at_configured_active_task_limit(monkeypatch):
    monkeypatch.setattr(settings, "MAX_CONCURRENT_JOBS_PER_USER", 3)
    db = FakeSession([FakeResult(None), FakeResult(3), FakeResult(99)])

    result = await admit_scrape_task(_user(), "https://example.com", db)

    assert isinstance(result, AdmissionError)
    assert result.error_type == AdmissionErrorType.TOO_MANY_ACTIVE_TASKS
    assert result.active_task_id == 99
    assert db.added is None
    assert db.commits == 0
    assert db.rollbacks == 1
