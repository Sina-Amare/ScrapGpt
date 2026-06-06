"""
Extended provider endpoint tests.

Covers: POST /providers/{id}/reveal-key, POST /providers/{id}/test
(success and failure paths), GET /providers (list), DELETE /providers/{id}.

The existing test_providers.py covers: auth-required, create (no key leak),
user-isolation on PATCH/DELETE/test, 409 conflict.
"""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import deps
from app.api.v1.endpoints import providers
from app.core.rate_limit import limiter
from app.core.security import hash_password
from app.models.provider_config import ProviderConfig
from app.models.user import User
from app.services import provider_service


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _provider(
    provider_id: int = 1,
    user_id: int = 1,
    name: str = "My OpenAI",
    capability_flags: dict | None = None,
    is_default: bool = True,
) -> ProviderConfig:
    encrypted_key = provider_service.encrypt_api_key("sk-test-key-12345")
    return ProviderConfig(
        id=provider_id,
        user_id=user_id,
        name=name,
        provider="openai",
        model="gpt-4o-mini",
        api_key_encrypted=encrypted_key,
        is_default=is_default,
        capability_flags=capability_flags or {},
        created_at=_now(),
        updated_at=_now(),
    )


class FakeDB:
    async def rollback(self):
        pass


@pytest.fixture
def app():
    application = FastAPI()
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    application.include_router(providers.router, prefix="/api/v1")
    return application


def _user(user_id: int = 1) -> User:
    return User(id=user_id, email="u@example.com", hashed_password=hash_password("correct-password"))


# ---------------------------------------------------------------------------
# GET /providers — list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_providers_returns_empty_list_when_no_providers(async_client, app, monkeypatch):
    async def fake_list(_db, _user_id):
        return []

    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield FakeDB())
    monkeypatch.setattr(providers.provider_service, "list_provider_configs", fake_list)

    response = await async_client.get("/api/v1/providers")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_providers_returns_all_user_providers(async_client, app, monkeypatch):
    p1 = _provider(provider_id=1, name="Primary")
    p2 = _provider(provider_id=2, name="Secondary", is_default=False)

    async def fake_list(_db, _user_id):
        return [p1, p2]

    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield FakeDB())
    monkeypatch.setattr(providers.provider_service, "list_provider_configs", fake_list)

    response = await async_client.get("/api/v1/providers")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["name"] == "Primary"
    assert "api_key" not in body[0]
    assert "api_key_encrypted" not in body[0]


# ---------------------------------------------------------------------------
# DELETE /providers/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_provider_returns_204(async_client, app, monkeypatch):
    p = _provider()

    async def fake_get_config(_db, user_id, provider_config_id):
        assert user_id == 1
        assert provider_config_id == 1
        return p

    deleted = []

    async def fake_delete(_db, _user_id, provider_config):
        deleted.append(provider_config)

    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield FakeDB())
    monkeypatch.setattr(providers.provider_service, "get_provider_config", fake_get_config)
    monkeypatch.setattr(providers.provider_service, "delete_provider_config", fake_delete)

    response = await async_client.delete("/api/v1/providers/1")

    assert response.status_code == 204
    assert len(deleted) == 1


@pytest.mark.asyncio
async def test_delete_provider_returns_404_when_not_found(async_client, app, monkeypatch):
    async def fake_get_config(_db, user_id, provider_config_id):
        return None

    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield FakeDB())
    monkeypatch.setattr(providers.provider_service, "get_provider_config", fake_get_config)

    response = await async_client.delete("/api/v1/providers/42")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /providers/{id}/reveal-key — reveal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reveal_key_requires_authentication(async_client, app):
    response = await async_client.post(
        "/api/v1/providers/1/reveal-key",
        json={"password": "correct-password"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_reveal_key_requires_correct_password(async_client, app, monkeypatch):
    p = _provider()  # encrypted key wraps "sk-test-key-12345"

    async def fake_get_config(_db, user_id, provider_config_id):
        return p

    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield FakeDB())
    monkeypatch.setattr(providers.provider_service, "get_provider_config", fake_get_config)

    response = await async_client.post(
        "/api/v1/providers/1/reveal-key",
        json={"password": "wrong-password"},
    )

    assert response.status_code == 401
    assert "sk-test-key-12345" not in response.text


@pytest.mark.asyncio
async def test_reveal_key_returns_decrypted_api_key_after_password_confirmation(
    async_client, app, monkeypatch
):
    p = _provider()  # encrypted key wraps "sk-test-key-12345"

    async def fake_get_config(_db, user_id, provider_config_id):
        return p

    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield FakeDB())
    monkeypatch.setattr(providers.provider_service, "get_provider_config", fake_get_config)

    response = await async_client.post(
        "/api/v1/providers/1/reveal-key",
        json={"password": "correct-password"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["api_key"] == "sk-test-key-12345"


@pytest.mark.asyncio
async def test_reveal_key_returns_404_for_other_users_provider(async_client, app, monkeypatch):
    """Ownership check: user 1 cannot reveal user 2's key."""

    async def fake_get_config(_db, user_id, provider_config_id):
        # service returns None when not owned by the requesting user
        return None

    app.dependency_overrides[deps.get_current_user] = lambda: _user(user_id=1)
    app.dependency_overrides[deps.get_db] = lambda: (yield FakeDB())
    monkeypatch.setattr(providers.provider_service, "get_provider_config", fake_get_config)

    response = await async_client.post(
        "/api/v1/providers/99/reveal-key",
        json={"password": "correct-password"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reveal_key_never_exposes_encrypted_blob(async_client, app, monkeypatch):
    """The raw encrypted bytes must not appear in the response."""
    p = _provider()

    async def fake_get_config(_db, user_id, provider_config_id):
        return p

    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield FakeDB())
    monkeypatch.setattr(providers.provider_service, "get_provider_config", fake_get_config)

    response = await async_client.post(
        "/api/v1/providers/1/reveal-key",
        json={"password": "correct-password"},
    )

    # The encrypted blob must not appear in the plaintext response
    assert p.api_key_encrypted not in response.text
    # Only the decrypted plaintext should appear
    assert "sk-test-key-12345" in response.text


# ---------------------------------------------------------------------------
# POST /providers/{id}/test — capability detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_test_provider_returns_capability_flags_on_success(async_client, app, monkeypatch):
    p = _provider()
    success_flags = {"connectivity": True, "validated_json": True, "native_json": True}

    async def fake_get_config(_db, user_id, provider_config_id):
        return p

    async def fake_test_config(_db, _provider):
        return True, success_flags, None

    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield FakeDB())
    monkeypatch.setattr(providers.provider_service, "get_provider_config", fake_get_config)
    monkeypatch.setattr(providers.provider_service, "test_provider_config", fake_test_config)

    response = await async_client.post("/api/v1/providers/1/test")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["capability_flags"]["connectivity"] is True
    assert body["capability_flags"]["validated_json"] is True
    assert body["capability_flags"]["native_json"] is True
    assert body["error"] is None


@pytest.mark.asyncio
async def test_test_provider_returns_error_detail_on_failure(async_client, app, monkeypatch):
    p = _provider()
    failure_flags = {
        "connectivity": False,
        "validated_json": False,
        "native_json": False,
        "error_type": "AuthenticationError",
        "error_detail": "Invalid API key",
    }

    async def fake_get_config(_db, user_id, provider_config_id):
        return p

    async def fake_test_config(_db, _provider):
        return False, failure_flags, "Invalid API key"

    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield FakeDB())
    monkeypatch.setattr(providers.provider_service, "get_provider_config", fake_get_config)
    monkeypatch.setattr(providers.provider_service, "test_provider_config", fake_test_config)

    response = await async_client.post("/api/v1/providers/1/test")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error"] == "Invalid API key"
    assert body["capability_flags"]["error_type"] == "AuthenticationError"
    assert body["capability_flags"]["connectivity"] is False


@pytest.mark.asyncio
async def test_test_provider_returns_404_when_provider_not_found(async_client, app, monkeypatch):
    async def fake_get_config(_db, user_id, provider_config_id):
        return None

    app.dependency_overrides[deps.get_current_user] = lambda: _user()
    app.dependency_overrides[deps.get_db] = lambda: (yield FakeDB())
    monkeypatch.setattr(providers.provider_service, "get_provider_config", fake_get_config)

    response = await async_client.post("/api/v1/providers/404/test")

    assert response.status_code == 404
