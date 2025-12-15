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
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    pass  # Future: from app.models.job import Job


class User(TimestampMixin, Base):
    """
    User model for the ScrapGPT platform.
    
    Handles authentication and daily credit management.
    Credits reset lazily - when checked after 24 hours have passed.
    
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
    # Relationships (Future)
    # -------------------------------------------------------------------------
    # jobs: Mapped[list["Job"]] = relationship("Job", back_populates="user")
    
    # -------------------------------------------------------------------------
    # Methods
    # -------------------------------------------------------------------------
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<User {self.email}>"
    
    def ensure_credits_reset(self) -> bool:
        """
        Reset credits if 24 hours have passed since last reset.
        
        This implements "lazy reset" - credits are only reset when
        this method is called, not via a scheduled job.
        
        Returns:
            bool: True if credits were reset, False otherwise
            
        Example:
            >>> user.ensure_credits_reset()
            True  # Credits were reset
            >>> user.ensure_credits_reset()
            False  # Less than 24h since last reset
        """
        now = datetime.now(timezone.utc)
        seconds_since_reset = (now - self.credits_reset_at).total_seconds()
        
        # 86400 seconds = 24 hours
        if seconds_since_reset >= 86400:
            self.credits_remaining = self.daily_credit_limit
            self.credits_reset_at = now
            return True
        
        return False
    
    def use_credit(self, amount: int = 1) -> bool:
        """
        Consume credits for a scraping operation.
        
        Automatically checks for daily reset before consuming.
        
        Args:
            amount: Number of credits to consume (default: 1)
            
        Returns:
            bool: True if credits were available and consumed, False otherwise
            
        Example:
            >>> user.credits_remaining = 5
            >>> user.use_credit()
            True
            >>> user.credits_remaining
            4
            >>> user.credits_remaining = 0
            >>> user.use_credit()
            False
        """
        # Check for daily reset first
        self.ensure_credits_reset()
        
        if self.credits_remaining >= amount:
            self.credits_remaining -= amount
            return True
        
        return False
    
    @property
    def has_credits(self) -> bool:
        """
        Check if user has any remaining credits.
        
        Automatically triggers daily reset check.
        
        Returns:
            bool: True if credits are available
        """
        self.ensure_credits_reset()
        return self.credits_remaining > 0
    
    @property
    def seconds_until_reset(self) -> float:
        """
        Calculate seconds remaining until next credit reset.
        
        Returns:
            float: Seconds until reset (0 if reset is available now)
        """
        now = datetime.now(timezone.utc)
        seconds_since_reset = (now - self.credits_reset_at).total_seconds()
        remaining = 86400 - seconds_since_reset
        return max(0, remaining)
