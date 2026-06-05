import inspect
from datetime import datetime, timedelta, timezone

from fastapi import Request as FastAPIRequest
from jose import jwt
from starlette.requests import Request

from app.api.v1.endpoints import auth
from app.core.config import settings
from app.core.rate_limit import get_user_identifier, limiter
from app.core.security import create_access_token


def _request_with_authorization(value: str | None) -> Request:
    headers = []
    if value is not None:
        headers.append((b"authorization", value.encode("ascii")))

    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
            "client": ("203.0.113.9", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


def test_rate_limit_identifier_uses_verified_access_token_subject() -> None:
    token = create_access_token(subject=123)

    assert get_user_identifier(_request_with_authorization(f"Bearer {token}")) == "user:123"


def test_rate_limit_identifier_ignores_forged_jwt_subject() -> None:
    forged_token = jwt.encode(
        {
            "sub": "victim-user",
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        "wrong-secret",
        algorithm=settings.JWT_ALGORITHM,
    )

    assert (
        get_user_identifier(_request_with_authorization(f"Bearer {forged_token}"))
        == "203.0.113.9"
    )


def test_refresh_endpoint_is_rate_limited_with_request_parameter() -> None:
    signature = inspect.signature(auth.refresh_token)
    endpoint_name = f"{auth.refresh_token.__module__}.{auth.refresh_token.__name__}"
    route_limits = limiter._route_limits.get(endpoint_name, [])

    assert signature.parameters["request"].annotation is FastAPIRequest
    assert any(
        limit.limit.amount == settings.RATE_LIMIT_AUTH_PER_MINUTE
        and limit.limit.get_expiry() == 60
        for limit in route_limits
    )
