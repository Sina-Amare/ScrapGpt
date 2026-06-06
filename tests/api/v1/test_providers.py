from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from sqlalchemy.exc import IntegrityError

from app.api import deps
from app.api.v1.endpoints import providers
from app.models.provider_config import ProviderConfig
from app.models.user import User


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(providers.router, prefix="/api/v1")
    return app


def _provider_config() -> ProviderConfig:
    now = datetime.now(timezone.utc)
    return ProviderConfig(
        id=1,
        user_id=1,
        name="OpenAI",
        provider="openai",
        model="gpt-4o-mini",
        api_key_encrypted="encrypted-secret",
        is_default=True,
        capability_flags={"validated_json": True},
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_provider_routes_require_auth(async_client):
    response = await async_client.get("/api/v1/providers")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_provider_response_never_exposes_api_key(async_client, app, monkeypatch):
    async def override_get_current_user():
        return User(id=1, email="user@example.com", hashed_password="hash")

    async def override_get_db():
        yield object()

    async def fake_create_provider_config(_db, user_id, payload):
        assert user_id == 1
        assert payload.api_key == "secret-api-key"
        return _provider_config()

    app.dependency_overrides[deps.get_current_user] = override_get_current_user
    app.dependency_overrides[deps.get_db] = override_get_db
    monkeypatch.setattr(
        providers.provider_service,
        "create_provider_config",
        fake_create_provider_config,
    )

    response = await async_client.post(
        "/api/v1/providers",
        json={
            "name": "OpenAI",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "api_key": "secret-api-key",
            "is_default": True,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["provider"] == "openai"
    assert "api_key" not in body
    assert "api_key_encrypted" not in body
    assert "secret-api-key" not in response.text
    assert "encrypted-secret" not in response.text


@pytest.mark.asyncio
async def test_provider_detail_is_scoped_to_current_user(async_client, app, monkeypatch):
    async def override_get_current_user():
        return User(id=1, email="user@example.com", hashed_password="hash")

    async def override_get_db():
        yield object()

    async def fake_get_provider_config(_db, user_id, provider_config_id):
        assert user_id == 1
        assert provider_config_id == 2
        return None

    app.dependency_overrides[deps.get_current_user] = override_get_current_user
    app.dependency_overrides[deps.get_db] = override_get_db
    monkeypatch.setattr(
        providers.provider_service,
        "get_provider_config",
        fake_get_provider_config,
    )

    response = await async_client.patch(
        "/api/v1/providers/2",
        json={"name": "Should not update"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_provider_conflict_returns_409(async_client, app, monkeypatch):
    class FakeDB:
        def __init__(self):
            self.rollbacks = 0

        async def rollback(self):
            self.rollbacks += 1

    fake_db = FakeDB()

    async def override_get_current_user():
        return User(id=1, email="user@example.com", hashed_password="hash")

    async def override_get_db():
        yield fake_db

    async def fake_create_provider_config(_db, _user_id, _payload):
        raise IntegrityError("INSERT", {}, Exception("duplicate default"))

    app.dependency_overrides[deps.get_current_user] = override_get_current_user
    app.dependency_overrides[deps.get_db] = override_get_db
    monkeypatch.setattr(
        providers.provider_service,
        "create_provider_config",
        fake_create_provider_config,
    )

    response = await async_client.post(
        "/api/v1/providers",
        json={
            "name": "OpenAI",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "api_key": "secret-api-key",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Provider configuration conflict"
    assert fake_db.rollbacks == 1


@pytest.mark.asyncio
async def test_user_cannot_access_other_user_provider_details(async_client, app, monkeypatch):
    async def override_get_current_user():
        return User(id=1, email="user@example.com", hashed_password="hash")

    async def override_get_db():
        yield object()

    async def fake_get_provider_config(_db, user_id, provider_config_id):
        assert user_id == 1
        assert provider_config_id == 999
        return None

    app.dependency_overrides[deps.get_current_user] = override_get_current_user
    app.dependency_overrides[deps.get_db] = override_get_db
    monkeypatch.setattr(
        providers.provider_service,
        "get_provider_config",
        fake_get_provider_config,
    )

    # Test UPDATE
    response = await async_client.patch(
        "/api/v1/providers/999",
        json={"name": "Attacker Update"},
    )
    assert response.status_code == 404

    # Test DELETE
    response = await async_client.delete("/api/v1/providers/999")
    assert response.status_code == 404

    # Test TEST
    response = await async_client.post("/api/v1/providers/999/test")
    assert response.status_code == 404

