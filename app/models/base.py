"""
SQLAlchemy base model and common mixins.

This module provides:
- Base declarative class for all models
- Common mixins for timestamps, soft delete, etc.
- Utility functions for models

Usage:
    from app.models.base import Base, TimestampMixin
    
    class User(TimestampMixin, Base):
        __tablename__ = "users"
        id = Column(Integer, primary_key=True)
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    
    All models should inherit from this class. It provides:
    - Automatic table naming from class name
    - Common configuration for all models
    - Type hints support via Mapped
    
    Example:
        class User(Base):
            __tablename__ = "users"
            id: Mapped[int] = mapped_column(primary_key=True)
            email: Mapped[str] = mapped_column(unique=True)
    """
    
    # Type annotation map for automatic type conversion
    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }
    
    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class TimestampMixin:
    """
    Mixin that adds created_at and updated_at timestamp columns.
    
    - created_at: Set automatically when record is created
    - updated_at: Updated automatically when record is modified
    
    Usage:
        class User(TimestampMixin, Base):
            __tablename__ = "users"
            id: Mapped[int] = mapped_column(primary_key=True)
    """
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class SoftDeleteMixin:
    """
    Mixin that adds soft delete capability.
    
    Instead of permanently deleting records, this marks them as deleted.
    Query filters should exclude deleted records by default.
    
    Usage:
        class User(SoftDeleteMixin, Base):
            __tablename__ = "users"
            id: Mapped[int] = mapped_column(primary_key=True)
        
        # Soft delete a user
        user.deleted_at = datetime.now(timezone.utc)
    """
    
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
        nullable=True,
    )
    
    @property
    def is_deleted(self) -> bool:
        """Check if the record has been soft deleted."""
        return self.deleted_at is not None
    
    def soft_delete(self) -> None:
        """Mark the record as deleted."""
        self.deleted_at = datetime.now(timezone.utc)
    
    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.deleted_at = None


class IDMixin:
    """
    Mixin that adds an auto-incrementing integer primary key.
    
    Usage:
        class User(IDMixin, Base):
            __tablename__ = "users"
            email: Mapped[str] = mapped_column(unique=True)
    """
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )


class TableNameMixin:
    """
    Mixin that automatically generates table name from class name.
    
    Converts CamelCase class names to snake_case table names.
    Example: UserProfile -> user_profile
    
    Usage:
        class UserProfile(TableNameMixin, Base):
            # __tablename__ will be "user_profile"
            id: Mapped[int] = mapped_column(primary_key=True)
    """
    
    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        """Generate table name from class name."""
        import re
        # Convert CamelCase to snake_case
        name = re.sub(r'(?<!^)(?=[A-Z])', '_', cls.__name__).lower()
        return name
