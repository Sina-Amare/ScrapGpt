"""Password reset code model.

One row per issued reset code. Only a *hash* of the 6-digit code is stored
(never the code itself). A code is valid until ``expires_at``, is single-use
(``consumed_at`` set once redeemed), and is rate-limited per code via
``attempt_count``. Rows cascade-delete with the owning user.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PasswordResetCode(Base):
    __tablename__ = "password_reset_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User")

    def __repr__(self) -> str:
        return f"<PasswordResetCode user_id={self.user_id} consumed={self.consumed_at is not None}>"
