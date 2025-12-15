"""
Application configuration using pydantic-settings.

This module provides type-safe configuration management by loading
settings from environment variables and .env files. All settings
are validated at startup, catching configuration errors early.

Usage:
    from app.core.config import settings
    
    print(settings.APP_NAME)
    print(settings.DATABASE_URL)
"""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Settings are loaded in this priority order:
    1. Environment variables
    2. .env file
    3. Default values defined here
    
    Attributes:
        APP_NAME: Display name for the application
        ENVIRONMENT: Current environment (development/staging/production)
        DEBUG: Enable debug mode and verbose logging
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore extra env vars not defined here
    )
    
    # -------------------------------------------------------------------------
    # Application Settings
    # -------------------------------------------------------------------------
    APP_NAME: str = "ScrapGPT"
    ENVIRONMENT: str = Field(default="development", pattern="^(development|staging|production)$")
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    
    # -------------------------------------------------------------------------
    # Server Settings
    # -------------------------------------------------------------------------
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    WORKERS: int = 1
    
    # -------------------------------------------------------------------------
    # Database Settings
    # -------------------------------------------------------------------------
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/scrapegpt",
        description="PostgreSQL connection URL with asyncpg driver"
    )
    DB_POOL_SIZE: int = Field(default=5, ge=1, le=50)
    DB_MAX_OVERFLOW: int = Field(default=10, ge=0, le=100)
    
    # -------------------------------------------------------------------------
    # Security Settings
    # -------------------------------------------------------------------------
    SECRET_KEY: str = Field(
        default="change-this-secret-key-in-prod-32chars",
        min_length=32,
        description="Secret key for JWT signing. Generate with: openssl rand -hex 32"
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=5, le=1440)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1, le=30)
    PASSWORD_HASH_ROUNDS: int = Field(default=12, ge=4, le=31)
    
    # -------------------------------------------------------------------------
    # CORS Settings
    # -------------------------------------------------------------------------
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS string into a list of origins."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    # -------------------------------------------------------------------------
    # Rate Limiting & Credits
    # -------------------------------------------------------------------------
    DEFAULT_USER_CREDITS: int = Field(default=100, ge=0)
    SCRAPE_CREDIT_COST: int = Field(default=1, ge=1)
    
    # -------------------------------------------------------------------------
    # Scraping Settings
    # -------------------------------------------------------------------------
    SCRAPE_TIMEOUT: int = Field(default=30, ge=5, le=300)
    MAX_CONCURRENT_JOBS: int = Field(default=5, ge=1, le=50)
    USER_AGENT: str = "ScrapGPT/1.0"
    
    # -------------------------------------------------------------------------
    # Logging Settings
    # -------------------------------------------------------------------------
    LOG_LEVEL: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    LOG_FORMAT: str = Field(default="text", pattern="^(json|text)$")
    
    # -------------------------------------------------------------------------
    # Computed Properties
    # -------------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT == "development"
    
    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Warn if using default secret key in non-development."""
        if v == "change-this-secret-key-in-prod-32chars":
            import warnings
            warnings.warn(
                "Using default SECRET_KEY! Generate a secure key for production.",
                UserWarning,
                stacklevel=2
            )
        return v


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Using lru_cache ensures settings are only loaded once per process,
    improving performance and ensuring consistency.
    
    Returns:
        Settings: The application settings instance
    """
    return Settings()


# Global settings instance for convenient access
settings = get_settings()
