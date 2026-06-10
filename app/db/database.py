"""
Async database connection and session management.

This module provides:
- Async SQLAlchemy engine with connection pooling
- AsyncSession factory for database operations
- Dependency for FastAPI route handlers

Usage:
    from app.db.database import get_db
    
    @router.get("/users")
    async def get_users(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(User))
        return result.scalars().all()
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings


# -----------------------------------------------------------------------------
# Database Engine Configuration
# -----------------------------------------------------------------------------

# Create async engine with connection pooling
# - echo: Log SQL statements (useful for debugging, disable in production)
# - pool_pre_ping: Verify connections before use (handles stale connections)
# - pool_size: Number of persistent connections to maintain
# - max_overflow: Additional connections allowed during peak load
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
)

# For testing, use NullPool to avoid connection issues
# Uncomment this for test configurations:
# test_engine = create_async_engine(
#     settings.DATABASE_URL,
#     echo=True,
#     poolclass=NullPool,
# )


# -----------------------------------------------------------------------------
# Session Factory
# -----------------------------------------------------------------------------

# async_sessionmaker creates AsyncSession instances
# - expire_on_commit=False: Prevents "detached instance" errors after commit
# - autocommit=False: Require explicit commits (safer, more predictable)
# - autoflush=False: Don't auto-flush before queries (more control)
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# -----------------------------------------------------------------------------
# Dependency Injection
# -----------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session.
    
    This is an async generator that:
    1. Creates a new session for each request
    2. Yields the session for use in route handlers
    3. Automatically closes the session when the request completes
    
    Usage:
        @router.get("/example")
        async def example_route(db: AsyncSession = Depends(get_db)):
            # Use db for database operations
            result = await db.execute(select(Model))
            return result.scalars().all()
    
    Yields:
        AsyncSession: A database session for the request
    """
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


# Type alias for cleaner dependency injection
# Usage: async def route(db: DatabaseSession): ...
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


# -----------------------------------------------------------------------------
# Database Lifecycle Functions
# -----------------------------------------------------------------------------

async def init_db() -> None:
    """
    Initialize database tables.
    
    This function creates all tables defined in the models.
    Only use for development/testing. In production, use Alembic migrations.
    
    Note: Import all models before calling this to ensure they're registered.
    """
    from app.models.base import Base
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """
    Close database connections.
    
    Call this during application shutdown to cleanly close
    all database connections in the pool.
    """
    await engine.dispose()
