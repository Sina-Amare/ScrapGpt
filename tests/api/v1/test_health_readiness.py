import pytest
from fastapi import FastAPI

from app.api import deps
from app.api.v1.endpoints import health
from app.services.readiness import DBReadinessResult


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(health.router, prefix="/api/v1")

    async def override_get_db():
        class DummySession:
            pass

        yield DummySession()

    app.dependency_overrides[deps.get_db] = override_get_db
    return app


@pytest.mark.asyncio
async def test_readiness_ok_returns_200(async_client, monkeypatch):
    async def fake_check(_db, _timeout_seconds):
        return DBReadinessResult(ready=True, code="ok")

    monkeypatch.setattr(health, "check_db_ready", fake_check)

    response = await async_client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["database"] == "ok"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason",
    ["db_unreachable", "schema_incompatible", "query_failed", "timeout"],
)
async def test_readiness_failure_returns_503(async_client, monkeypatch, reason):
    async def fake_check(_db, _timeout_seconds):
        return DBReadinessResult(ready=False, code=reason)

    monkeypatch.setattr(health, "check_db_ready", fake_check)

    response = await async_client.get("/api/v1/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["database"] == reason


@pytest.mark.asyncio
async def test_readiness_response_is_sanitized(async_client, monkeypatch):
    async def fake_check(_db, _timeout_seconds):
        return DBReadinessResult(ready=False, code="query_failed")

    monkeypatch.setattr(health, "check_db_ready", fake_check)

    response = await async_client.get("/api/v1/health/ready")

    assert response.status_code == 503
    body_text = response.text.lower()
    assert "postgresql://" not in body_text
    assert "password" not in body_text
    assert "user:pass@" not in body_text

