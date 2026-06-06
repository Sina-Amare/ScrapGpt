import pytest
from pydantic import BaseModel

from app.models.provider_config import ProviderConfig
from app.services import provider_service


class Probe(BaseModel):
    ok: bool


def _provider_config() -> ProviderConfig:
    return ProviderConfig(
        id=1,
        user_id=1,
        name="Test provider",
        provider="openai",
        model="gpt-4o-mini",
        api_key_encrypted=provider_service.encrypt_api_key("secret-api-key"),
        is_default=True,
        capability_flags={},
    )


def test_encrypt_api_key_round_trips_without_plaintext_storage():
    encrypted = provider_service.encrypt_api_key("secret-api-key")

    assert encrypted != "secret-api-key"
    assert "secret-api-key" not in encrypted
    assert provider_service.decrypt_api_key(encrypted) == "secret-api-key"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"ok": true}', {"ok": True}),
        ('```json\n{"ok": true}\n```', {"ok": True}),
        ('Here is JSON:\n{"ok": true}\nDone.', {"ok": True}),
    ],
)
def test_extract_json_payload_handles_common_provider_formats(raw, expected):
    assert provider_service.extract_json_payload(raw) == expected


def test_validate_json_response_rejects_schema_mismatch():
    with pytest.raises(provider_service.ProviderJSONError):
        provider_service.validate_json_response('{"wrong": true}', Probe)


@pytest.mark.asyncio
async def test_call_json_model_falls_back_when_native_json_is_rejected(monkeypatch):
    calls = []

    async def fake_completion(provider_config, api_key, messages, response_format=None):
        calls.append(
            {
                "api_key": api_key,
                "messages": messages,
                "response_format": response_format,
            }
        )
        if response_format is not None:
            raise provider_service.ProviderCallError("unsupported response_format")
        return '{"ok": true}'

    monkeypatch.setattr(provider_service, "_completion", fake_completion)

    result = await provider_service.call_json_model(
        _provider_config(),
        [{"role": "user", "content": "Return JSON."}],
        Probe,
    )

    assert result.data.ok is True
    assert result.used_native_json is False
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert calls[1]["response_format"] is None
    assert calls[1]["api_key"] == "secret-api-key"
    assert "Output ONLY raw JSON" in calls[1]["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_call_json_model_retries_invalid_json_then_valid(monkeypatch):
    responses = ["not json", '```json\n{"ok": true}\n```']

    async def fake_completion(_provider_config, _api_key, _messages, response_format=None):
        return responses.pop(0)

    monkeypatch.setattr(provider_service, "_completion", fake_completion)

    result = await provider_service.call_json_model(
        _provider_config(),
        [{"role": "user", "content": "Return JSON."}],
        Probe,
    )

    assert result.data.ok is True
    assert result.used_native_json is False
