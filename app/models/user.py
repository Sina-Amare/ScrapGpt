"""
User model for authentication and credit management.

This module defines the User model with:
- Authentication fields (email, password hash)
- Daily credit system with lazy reset
- Account status tracking

Usage:
    from app.models.user import User
    
    user = User(
        email="user@example.com",
        hashed_password=hash_password("secret"),
    )
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    pass  # Future: from app.models.job import Job


class User(TimestampMixin, Base):
    """
    User model for the ScrapGPT platform.

    Handles authentication and daily credit management.
    Credits reset at 00:00 UTC daily via scheduled job.

    Attributes:
        id: Primary key
        email: Unique login identifier
        hashed_password: bcrypt password hash
        is_active: Whether the account can be used
        is_verified: Whether email has been verified
        credits_remaining: Current available credits
        daily_credit_limit: Max credits per day (allows per-user limits)
        credits_reset_at: When credits were last reset (UTC)

    Example:
        >>> user = User(email="test@example.com", hashed_password="...")
        >>> user.credits_remaining
        5
        >>> user.use_credit()
        True
        >>> user.credits_remaining
        4
    """
    
    __tablename__ = "users"
    
    # -------------------------------------------------------------------------
    # Primary Key
    # -------------------------------------------------------------------------
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    
    # -------------------------------------------------------------------------
    # Authentication Fields
    # -------------------------------------------------------------------------
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User's email address (login identifier)",
    )
    
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="bcrypt hashed password",
    )
    
    # -------------------------------------------------------------------------
    # Account Status
    # -------------------------------------------------------------------------
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
        index=True,
        comment="Whether the account is enabled",
    )
    
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
        comment="Whether email has been verified",
    )
    
    # -------------------------------------------------------------------------
    # Credit System
    # -------------------------------------------------------------------------
    credits_remaining: Mapped[int] = mapped_column(
        Integer,
        default=5,
        server_default="5",
        nullable=False,
        comment="Current available daily credits",
    )
    
    daily_credit_limit: Mapped[int] = mapped_column(
        Integer,
        default=5,
        server_default="5",
        nullable=False,
        comment="Maximum credits per day (can be increased for premium)",
    )
    
    credits_reset_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        comment="When credits were last reset (UTC)",
    )
    
    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    scrape_tasks = relationship(
        "ScrapeTask",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    
    # -------------------------------------------------------------------------
    # Methods
    # -------------------------------------------------------------------------

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<User {self.email}>"

    def ensure_credits_reset(self) -> bool:
        """
        DEPRECATED: Credits now reset at 00:00 UTC via scheduler.

        This method is kept for backwards compatibility but should not be used.
        It always returns False since lazy reset is no longer the policy.
        """
        import warnings
        warnings.warn(
            "ensure_credits_reset is deprecated. "
            "Credits reset at 00:00 UTC via scheduler.",
            DeprecationWarning,
            stacklevel=2,
        )
        return False

    def use_credit(self, amount: int = 1) -> bool:
        """
        Consume credits for a scraping operation.

        NOTE: This method does NOT trigger lazy reset anymore.
        Credits reset at 00:00 UTC daily via scheduler.

        Args:
            amount: Number of credits to consume (default: 1)

        Returns:
            bool: True if credits were available and consumed, False otherwise
        """
        if self.credits_remaining >= amount:
            self.credits_remaining -= amount
            return True
        return False

    @property
    def has_credits(self) -> bool:
        """
        Check if user has any remaining credits.

        NOTE: Does NOT trigger lazy reset - credits reset at 00:00 UTC.

        Returns:
            bool: True if credits are available
        """
        return self.credits_remaining > 0

    @property
    def seconds_until_reset(self) -> float:
        """
        Calculate seconds remaining until next credit reset.

        Credits reset at 00:00 UTC daily.

        Returns:
            float: Seconds until next 00:00 UTC
        """
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        # Calculate seconds until next midnight UTC
        seconds_today = (
            now.hour * 3600 + now.minute * 60 + now.second
        )
        seconds_in_day = 86400
        return seconds_in_day - seconds_today

