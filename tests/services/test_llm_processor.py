"""
Unit tests for llm_processor.process_with_llm.

Mocks both the database session (via _get_provider) and call_json_model
so no real network calls are made.
"""

from unittest.mock import AsyncMock

import pytest

from app.models.provider_config import ProviderConfig
from app.services import llm_processor
from app.services.llm_processor import (
    ContentAnalysisResult,
    LLMError,
    _LLM_CONTENT_LIMIT,
    process_with_llm,
)
from app.services.provider_service import (
    ProviderCallError,
    JSONCallResult,
    encrypt_api_key,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _provider(provider_id: int = 1, name: str = "TestProvider") -> ProviderConfig:
    return ProviderConfig(
        id=provider_id,
        user_id=1,
        name=name,
        provider="openai",
        model="gpt-4o-mini",
        api_key_encrypted=encrypt_api_key("sk-test"),
        is_default=True,
        capability_flags={},
    )


def _analysis_result(**kwargs) -> ContentAnalysisResult:
    defaults = dict(
        summary="A test page about widgets.",
        key_points=["Point A", "Point B"],
        data_type="article",
        word_count=150,
    )
    return ContentAnalysisResult(**(defaults | kwargs))


def _json_call_result(analysis: ContentAnalysisResult, used_native: bool = True) -> JSONCallResult:
    return JSONCallResult(
        data=analysis,
        used_native_json=used_native,
        raw_response='{"summary":"..."}',
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_with_llm_raises_llm_error_when_no_provider_configured(monkeypatch):
    monkeypatch.setattr(llm_processor, "_get_provider", AsyncMock(return_value=None))

    with pytest.raises(LLMError, match="No AI provider configured"):
        await process_with_llm("some content", user_id=1)


@pytest.mark.asyncio
async def test_process_with_llm_returns_analysis_dict_on_success(monkeypatch):
    analysis = _analysis_result()
    monkeypatch.setattr(llm_processor, "_get_provider", AsyncMock(return_value=_provider()))
    monkeypatch.setattr(
        llm_processor, "call_json_model", AsyncMock(return_value=_json_call_result(analysis))
    )

    result = await process_with_llm("some content", user_id=1)

    assert result["summary"] == "A test page about widgets."
    assert result["key_points"] == ["Point A", "Point B"]
    assert result["data_type"] == "article"
    assert result["word_count"] == 150


@pytest.mark.asyncio
async def test_process_with_llm_truncates_content_to_limit(monkeypatch):
    captured_messages = []

    async def fake_call_json_model(provider, messages, schema, max_retries=3):
        captured_messages.extend(messages)
        return _json_call_result(_analysis_result())

    monkeypatch.setattr(llm_processor, "_get_provider", AsyncMock(return_value=_provider()))
    monkeypatch.setattr(llm_processor, "call_json_model", fake_call_json_model)

    long_content = "x" * (_LLM_CONTENT_LIMIT + 5000)
    await process_with_llm(long_content, user_id=1)

    # The content embedded in the user message should not exceed the limit
    user_message_content = captured_messages[0]["content"]
    # The truncated content is embedded after "Content:\n"
    content_section = user_message_content.split("Content:\n", 1)[1]
    assert len(content_section) == _LLM_CONTENT_LIMIT


@pytest.mark.asyncio
async def test_process_with_llm_raises_llm_error_on_provider_call_failure(monkeypatch):
    monkeypatch.setattr(llm_processor, "_get_provider", AsyncMock(return_value=_provider()))
    monkeypatch.setattr(
        llm_processor,
        "call_json_model",
        AsyncMock(side_effect=ProviderCallError("Network error")),
    )

    with pytest.raises(LLMError, match="failed"):
        await process_with_llm("content", user_id=1)


@pytest.mark.asyncio
async def test_process_with_llm_includes_provider_name_in_error(monkeypatch):
    provider = _provider(name="MyGPT")
    monkeypatch.setattr(llm_processor, "_get_provider", AsyncMock(return_value=provider))
    monkeypatch.setattr(
        llm_processor,
        "call_json_model",
        AsyncMock(side_effect=ProviderCallError("rate limit exceeded")),
    )

    with pytest.raises(LLMError, match="MyGPT"):
        await process_with_llm("content", user_id=1)


@pytest.mark.asyncio
async def test_process_with_llm_redacts_provider_key_from_error(monkeypatch):
    provider = _provider(name="MyGPT")
    monkeypatch.setattr(llm_processor, "_get_provider", AsyncMock(return_value=provider))
    monkeypatch.setattr(
        llm_processor,
        "call_json_model",
        AsyncMock(side_effect=ProviderCallError("Provider failed with sk-test")),
    )

    with pytest.raises(LLMError) as exc:
        await process_with_llm("content", user_id=1)

    assert "sk-test" not in str(exc.value)
    assert "MyGPT" in str(exc.value)


@pytest.mark.asyncio
async def test_process_with_llm_passes_user_id_to_get_provider(monkeypatch):
    called_with = []

    async def fake_get_provider(user_id: int):
        called_with.append(user_id)
        return None  # raise LLMError — we just care that it was called correctly

    monkeypatch.setattr(llm_processor, "_get_provider", fake_get_provider)

    with pytest.raises(LLMError):
        await process_with_llm("content", user_id=42)

    assert called_with == [42]


@pytest.mark.asyncio
async def test_process_with_llm_uses_fallback_provider_when_no_default(monkeypatch):
    """_get_provider is responsible for fallback; process_with_llm just uses whatever is returned."""
    fallback_provider = _provider(name="FallbackProvider")
    monkeypatch.setattr(
        llm_processor, "_get_provider", AsyncMock(return_value=fallback_provider)
    )
    monkeypatch.setattr(
        llm_processor,
        "call_json_model",
        AsyncMock(return_value=_json_call_result(_analysis_result())),
    )

    result = await process_with_llm("content", user_id=1)
    assert isinstance(result, dict)
    assert "summary" in result


@pytest.mark.asyncio
async def test_content_analysis_result_schema_validates_correctly():
    """ContentAnalysisResult must reject missing required fields."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ContentAnalysisResult(
            # missing summary, data_type, word_count
            key_points=["ok"],
        )


@pytest.mark.asyncio
async def test_content_analysis_result_word_count_cannot_be_negative():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ContentAnalysisResult(
            summary="test",
            key_points=[],
            data_type="article",
            word_count=-1,
        )
