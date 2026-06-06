import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_accepts_valid_provider_key_encryption_secret():
    settings = Settings(
        PROVIDER_KEY_ENCRYPTION_SECRET=Fernet.generate_key().decode(),
        _env_file=None,
    )

    assert settings.PROVIDER_KEY_ENCRYPTION_SECRET


@pytest.mark.parametrize("value", ["", "not-a-fernet-key", "short"])
def test_settings_rejects_invalid_provider_key_encryption_secret(value):
    with pytest.raises(ValidationError):
        Settings(PROVIDER_KEY_ENCRYPTION_SECRET=value, _env_file=None)


def test_settings_requires_provider_key_encryption_secret(monkeypatch):
    monkeypatch.delenv("PROVIDER_KEY_ENCRYPTION_SECRET", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
