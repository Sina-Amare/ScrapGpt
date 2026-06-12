"""Endpoint tests for the password-reset flow and /auth/config.

Covers the endpoint contract: a generic enumeration-safe response on request,
a generic 400 on confirm failure, rate limiting, and the public config flag.
The service layer is monkeypatched here; its invariants are tested in
tests/services/test_password_reset.py.
"""

import pytest
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import deps
from app.api.v1.endpoints import auth
from app.core.rate_limit import limiter
from app.services.password_reset import PasswordResetError


@pytest.fixture(autouse=True)
def _reset_limiter():
    try:
        limiter._storage.reset()
    except Exception:
        pass
    yield


@pytest.fixture
def app():
    application = FastAPI()
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    application.include_router(auth.router, prefix="/api/v1")
    application.dependency_overrides[deps.get_db] = lambda: (yield object())
    return application


@pytest.mark.asyncio
async def test_request_returns_generic_success(async_client, app, monkeypatch):
    seen = {}

    async def fake_request(_db, email):
        seen["email"] = email

    monkeypatch.setattr(auth, "request_password_reset", fake_request)

    response = await async_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "user@example.com"},
    )

    assert response.status_code == 200
    assert "reset code" in response.json()["message"].lower()
    assert seen["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_request_is_generic_even_for_unknown_email(async_client, app, monkeypatch):
    async def fake_request(_db, _email):
        return None  # service is silent for unknown emails

    monkeypatch.setattr(auth, "request_password_reset", fake_request)

    known = await async_client.post(
        "/api/v1/auth/password-reset/request", json={"email": "known@example.com"}
    )
    monkeypatch.setattr(auth, "request_password_reset", fake_request)
    unknown = await async_client.post(
        "/api/v1/auth/password-reset/request", json={"email": "ghost@example.com"}
    )

    # Identical status + body regardless of whether the email exists.
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


@pytest.mark.asyncio
async def test_confirm_success_returns_200(async_client, app, monkeypatch):
    async def fake_confirm(_db, _email, _code, _pw):
        return None

    monkeypatch.setattr(auth, "confirm_password_reset", fake_confirm)

    response = await async_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"email": "user@example.com", "code": "123456", "new_password": "new-password"},
    )

    assert response.status_code == 200
    assert "reset" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_confirm_failure_returns_generic_400(async_client, app, monkeypatch):
    async def fake_confirm(_db, _email, _code, _pw):
        raise PasswordResetError("TOO_MANY_ATTEMPTS")

    monkeypatch.setattr(auth, "confirm_password_reset", fake_confirm)

    response = await async_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"email": "user@example.com", "code": "999999", "new_password": "new-password"},
    )

    assert response.status_code == 400
    # The reason (too many attempts vs wrong code) is not leaked.
    assert "TOO_MANY_ATTEMPTS" not in response.text
    assert "invalid or has expired" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_request_is_rate_limited(async_client, app, monkeypatch):
    async def fake_request(_db, _email):
        return None

    monkeypatch.setattr(auth, "request_password_reset", fake_request)

    statuses = []
    for _ in range(6):
        resp = await async_client.post(
            "/api/v1/auth/password-reset/request", json={"email": "user@example.com"}
        )
        statuses.append(resp.status_code)

    # AUTH_RATE_LIMIT defaults to 5/minute -> the 6th request is throttled.
    assert statuses[:5] == [200, 200, 200, 200, 200]
    assert statuses[5] == 429


@pytest.mark.asyncio
async def test_auth_config_reports_password_reset_flag(async_client, app):
    response = await async_client.get("/api/v1/auth/config")
    assert response.status_code == 200
    assert "password_reset_enabled" in response.json()
    assert isinstance(response.json()["password_reset_enabled"], bool)
