"""Provider configuration schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProviderConfigCreate(BaseModel):
    """Create a user-owned provider config."""

    name: str = Field(..., min_length=1, max_length=120)
    provider: str = Field(..., min_length=1, max_length=80)
    model: str = Field(..., min_length=1, max_length=160)
    api_key: str = Field(..., min_length=1, max_length=4096)
    is_default: bool = False


class ProviderConfigUpdate(BaseModel):
    """Update a provider config. API key is write-only when present."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    provider: str | None = Field(default=None, min_length=1, max_length=80)
    model: str | None = Field(default=None, min_length=1, max_length=160)
    api_key: str | None = Field(default=None, min_length=1, max_length=4096)
    is_default: bool | None = None


class ProviderConfigResponse(BaseModel):
    """Provider config response without API key material."""

    id: int
    name: str
    provider: str
    model: str
    is_default: bool
    capability_flags: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProviderTestResponse(BaseModel):
    """Result of provider connectivity and capability detection."""

    ok: bool
    provider_config_id: int
    capability_flags: dict[str, Any]
    error: str | None = None
