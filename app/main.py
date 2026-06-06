"""
ScrapGPT - FastAPI Application Entry Point

This is the main entry point for the ScrapGPT API.
It initializes the FastAPI application with all middleware,
routes, and lifecycle handlers.

Usage:
    # Development
    uvicorn app.main:app --reload
    
    # Production
    gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.db.database import close_db


# -----------------------------------------------------------------------------
# Application Lifespan
# -----------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.
    
    This handles startup and shutdown events:
    - Startup: Initialize connections, warm up caches
    - Shutdown: Close connections, cleanup resources
    
    Args:
        app: The FastAPI application instance
        
    Yields:
        None: Control is passed to the application
    """
    # -------------------------------------------------------------------------
    # Startup
    # -------------------------------------------------------------------------
    print(f"🚀 Starting {settings.APP_NAME}...")
    print(f"📍 Environment: {settings.ENVIRONMENT}")
    print(f"🔧 Debug mode: {settings.DEBUG}")

    # Start background scheduler
    from app.core.scheduler import start_scheduler
    start_scheduler()
    print("⏰ Scheduler started")

    yield  # Application runs here

    # -------------------------------------------------------------------------
    # Shutdown
    # -------------------------------------------------------------------------
    print(f"🛑 Shutting down {settings.APP_NAME}...")

    # Stop scheduler
    from app.core.scheduler import stop_scheduler
    stop_scheduler()

    # Close database connections
    await close_db()

    print("👋 Shutdown complete")


# -----------------------------------------------------------------------------
# Application Factory
# -----------------------------------------------------------------------------

def create_app() -> FastAPI:
    """
    Application factory function.
    
    Creates and configures the FastAPI application with all
    middleware, routes, and settings.
    
    Returns:
        FastAPI: The configured application instance
    """
    app = FastAPI(
        title=settings.APP_NAME,
        description=(
            "A professional web scraping API with AI capabilities. "
            "Features include JWT authentication, BYOK provider management, "
            "and async job processing."
        ),
        version="0.1.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )
    
    # -------------------------------------------------------------------------
    # Middleware
    # -------------------------------------------------------------------------

    # CORS Middleware
    # Allows cross-origin requests from specified origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate Limiting Middleware
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from app.core.rate_limit import limiter

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    # -------------------------------------------------------------------------
    # Routes
    # -------------------------------------------------------------------------
    
    # Include API v1 router
    app.include_router(
        api_v1_router,
        prefix=settings.API_V1_PREFIX,
    )
    
    # Root endpoint for basic info
    @app.get("/", include_in_schema=False)
    async def root():
        """Root endpoint with basic API information."""
        return {
            "name": settings.APP_NAME,
            "version": "0.1.0",
            "docs": "/docs" if settings.DEBUG else None,
            "health": f"{settings.API_V1_PREFIX}/health",
        }
    
    return app


# -----------------------------------------------------------------------------
# Create Application Instance
# -----------------------------------------------------------------------------

# This is the ASGI application instance that Uvicorn will serve
app = create_app()


# -----------------------------------------------------------------------------
# Development Server
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=settings.WORKERS if not settings.DEBUG else 1,
    )
