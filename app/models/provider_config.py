"""Provider configuration model for user-owned BYOK credentials."""

from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ProviderConfig(TimestampMixin, Base):
    """User-owned AI provider configuration with encrypted API key storage."""

    __tablename__ = "provider_configs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    capability_flags: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )

    user = relationship(
        "User",
        back_populates="provider_configs",
        foreign_keys=[user_id],
    )

    def __repr__(self) -> str:
        return f"<ProviderConfig {self.id} provider={self.provider} model={self.model}>"
