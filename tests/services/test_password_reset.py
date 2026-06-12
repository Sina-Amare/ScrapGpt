"""Tests for the password-reset service invariants (Tier A).

Covers: enumeration-safety, code hashed at rest, expiry, attempt cap,
single-use, and that a successful reset stamps password_changed_at (which
invalidates existing tokens). Uses a small stateful fake session so the logic
is exercised without a live database.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.sql import Update

from app.core.security import (
    hash_password,
    token_predates_password_change,
    verify_password,
)
from app.models.password_reset import PasswordResetCode
from app.models.user import User
from app.services import password_reset as pr
from app.services.password_reset import (
    PasswordResetError,
    confirm_password_reset,
    request_password_reset,
)


# ---------------------------------------------------------------------------
# Fake session
# ---------------------------------------------------------------------------


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def first(self):
        return self._value


class FakeSession:
    """Returns a configured user/code and records adds + commits.

    Simulates the ``consumed_at IS NULL`` filter so single-use can be tested.
    """

    def __init__(self, user: User | None = None, code: PasswordResetCode | None = None):
        self.user = user
        self.code = code
        self.added: list = []
        self.commits = 0

    async def execute(self, statement):
        if isinstance(statement, Update):
            return _Result(None)
        entity = statement.column_descriptions[0]["entity"]
        if entity is User:
            return _Result(self.user)
        active_code = (
            self.code if (self.code is not None and self.code.consumed_at is None) else None
        )
        return _Result(active_code)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


def _user(user_id: int = 1, is_active: bool = True) -> User:
    return User(
        id=user_id,
        email="user@example.com",
        hashed_password=hash_password("old-password"),
        is_active=is_active,
    )


def _code(plain: str, *, expires_in_minutes: int = 15, attempts: int = 0) -> PasswordResetCode:
    return PasswordResetCode(
        id=1,
        user_id=1,
        code_hash=hash_password(plain),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
        attempt_count=attempts,
        consumed_at=None,
    )


@pytest.fixture(autouse=True)
def _no_email(monkeypatch):
    async def _fake_send(*_args, **_kwargs):
        return True

    monkeypatch.setattr(pr, "send_email", _fake_send)


# ---------------------------------------------------------------------------
# request_password_reset
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_unknown_email_is_silent_noop():
    db = FakeSession(user=None)
    await request_password_reset(db, "nobody@example.com")
    assert db.added == []
    assert db.commits == 0


@pytest.mark.asyncio
async def test_request_inactive_user_is_silent_noop():
    db = FakeSession(user=_user(is_active=False))
    await request_password_reset(db, "user@example.com")
    assert db.added == []


@pytest.mark.asyncio
async def test_request_stores_only_a_hash_with_expiry():
    db = FakeSession(user=_user())
    await request_password_reset(db, "user@example.com")

    assert len(db.added) == 1
    stored = db.added[0]
    assert isinstance(stored, PasswordResetCode)
    # The stored value is a bcrypt hash, not the plaintext 6-digit code.
    assert stored.code_hash.startswith("$2")
    assert not stored.code_hash.isdigit()
    assert stored.expires_at > datetime.now(timezone.utc)
    assert db.commits >= 1


# ---------------------------------------------------------------------------
# confirm_password_reset
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_success_updates_password_and_consumes_code():
    user = _user()
    code = _code("123456")
    db = FakeSession(user=user, code=code)

    await confirm_password_reset(db, "user@example.com", "123456", "brand-new-pass")

    assert verify_password("brand-new-pass", user.hashed_password)
    assert user.password_changed_at is not None
    assert code.consumed_at is not None  # single-use


@pytest.mark.asyncio
async def test_confirm_is_single_use():
    user = _user()
    code = _code("123456")
    db = FakeSession(user=user, code=code)
    await confirm_password_reset(db, "user@example.com", "123456", "brand-new-pass")

    # Code is now consumed; the filtered lookup returns nothing on reuse.
    with pytest.raises(PasswordResetError):
        await confirm_password_reset(db, "user@example.com", "123456", "another-pass")


@pytest.mark.asyncio
async def test_confirm_wrong_code_increments_attempts_and_raises():
    user = _user()
    code = _code("123456")
    db = FakeSession(user=user, code=code)

    with pytest.raises(PasswordResetError):
        await confirm_password_reset(db, "user@example.com", "000000", "brand-new-pass")

    assert code.attempt_count == 1
    assert code.consumed_at is None
    assert verify_password("old-password", user.hashed_password)  # unchanged


@pytest.mark.asyncio
async def test_confirm_expired_code_raises():
    user = _user()
    code = _code("123456", expires_in_minutes=-1)
    db = FakeSession(user=user, code=code)

    with pytest.raises(PasswordResetError):
        await confirm_password_reset(db, "user@example.com", "123456", "brand-new-pass")
    assert verify_password("old-password", user.hashed_password)


@pytest.mark.asyncio
async def test_confirm_too_many_attempts_burns_code():
    user = _user()
    code = _code("123456", attempts=5)
    db = FakeSession(user=user, code=code)

    with pytest.raises(PasswordResetError) as exc:
        await confirm_password_reset(db, "user@example.com", "123456", "brand-new-pass")
    assert exc.value.code == "TOO_MANY_ATTEMPTS"
    assert code.consumed_at is not None


@pytest.mark.asyncio
async def test_confirm_unknown_email_raises():
    db = FakeSession(user=None)
    with pytest.raises(PasswordResetError):
        await confirm_password_reset(db, "nobody@example.com", "123456", "x" * 10)


# ---------------------------------------------------------------------------
# Decision C: token invalidation helper
# ---------------------------------------------------------------------------


def test_token_predates_password_change():
    base = datetime(2026, 6, 12, 12, 0, 0, tzinfo=timezone.utc)
    base_ts = int(base.timestamp())

    # No password change yet -> never predates.
    assert token_predates_password_change(base_ts, None) is False
    # Token issued before the change -> rejected.
    assert token_predates_password_change(base_ts - 10, base) is True
    # Token issued at/after the change -> accepted.
    assert token_predates_password_change(base_ts, base) is False
    assert token_predates_password_change(base_ts + 10, base) is False
    # Legacy token without iat, after a change -> rejected.
    assert token_predates_password_change(None, base) is True
