"""LLM processing via the user's configured BYOK provider."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.db.database import async_session_factory
from app.models.provider_config import ProviderConfig
from app.services.provider_service import (
    ProviderServiceError,
    call_json_model,
    decrypt_api_key,
    safe_provider_error_message,
)


logger = logging.getLogger(__name__)

# Maximum characters of scraped content forwarded to the LLM.
# Keeps token costs manageable and avoids context-length errors on smaller models.
_LLM_CONTENT_LIMIT = 8_000


class LLMError(Exception):
    """Raised when LLM processing fails."""


class ContentAnalysisResult(BaseModel):
    """Structured analysis of a scraped page, produced by the LLM."""

    summary: str = Field(
        ...,
        description="2–3 sentence summary of the page content",
    )
    key_points: list[str] = Field(
        default_factory=list,
        description="Up to 5 key points extracted from the content",
    )
    data_type: str = Field(
        ...,
        description=(
            "Content classification: article, product, listing, documentation, or other"
        ),
    )
    word_count: int = Field(
        ...,
        description="Approximate word count of the input content",
        ge=0,
    )


async def _get_provider(user_id: int) -> ProviderConfig | None:
    """Return the user's default provider, or their first configured one if none is set."""
    async with async_session_factory() as db:
        result = await db.execute(
            select(ProviderConfig)
            .where(
                ProviderConfig.user_id == user_id,
                ProviderConfig.is_default.is_(True),
            )
            .limit(1)
        )
        provider = result.scalar_one_or_none()
        if provider is not None:
            return provider

        # Fall back to any provider the user has configured
        result = await db.execute(
            select(ProviderConfig)
            .where(ProviderConfig.user_id == user_id)
            .order_by(ProviderConfig.created_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def process_with_llm(content: str, user_id: int) -> dict[str, Any]:
    """
    Analyze scraped content using the user's BYOK provider.

    Fetches the user's default (or first) provider, caps the content at
    _LLM_CONTENT_LIMIT characters, and calls call_json_model with a
    ContentAnalysisResult schema.  Up to 3 retries with schema validation.

    Args:
        content: Raw text extracted from the scraped page.
        user_id: Owner — used to look up the provider config.

    Returns:
        ContentAnalysisResult serialised as a plain dict.

    Raises:
        LLMError: No provider configured, or call failed after retries.
    """
    logger.info("llm.processing", extra={"user_id": user_id, "content_length": len(content)})

    provider = await _get_provider(user_id)
    if provider is None:
        raise LLMError(
            "No AI provider configured. "
            "Add one in Settings before starting a scrape."
        )

    truncated = content[:_LLM_CONTENT_LIMIT]

    messages = [
        {
            "role": "user",
            "content": (
                "Analyze the following web page content and return a JSON object with:\n"
                '- "summary": a 2-3 sentence summary (string)\n'
                '- "key_points": up to 5 key points (array of strings)\n'
                '- "data_type": one of article, product, listing, documentation, or other (string)\n'
                '- "word_count": approximate integer word count\n\n'
                f"Content:\n{truncated}"
            ),
        }
    ]

    try:
        call_result = await call_json_model(
            provider,
            messages,
            ContentAnalysisResult,
            max_retries=3,
        )
        logger.info(
            "llm.completed",
            extra={
                "user_id": user_id,
                "provider_id": provider.id,
                "used_native_json": call_result.used_native_json,
                "data_type": call_result.data.data_type,
            },
        )
        return call_result.data.model_dump()

    except ProviderServiceError as exc:
        api_key = None
        try:
            api_key = decrypt_api_key(provider.api_key_encrypted)
        except Exception:
            api_key = None
        safe_error = safe_provider_error_message(exc, api_key)
        logger.error(
            "llm.provider_error",
            extra={"user_id": user_id, "provider_id": provider.id, "error": safe_error},
        )
        raise LLMError(f"Provider '{provider.name}' failed: {safe_error}") from exc

    except Exception as exc:
        safe_error = safe_provider_error_message(exc)
        logger.error("llm.unexpected_error", extra={"user_id": user_id, "error": safe_error})
        raise LLMError(f"LLM processing failed: {safe_error}") from exc
