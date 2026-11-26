from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_INSECURE_SECRET = "dev-insecure-secret-key-change-me-before-production"


class Settings(BaseSettings):
    """Application settings with fail-fast validation across environments."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "TaskHub API"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # Server & CORS
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Database
    database_url: str = "postgresql+asyncpg://taskhub:taskhub@localhost:5432/taskhub"
    db_echo: bool = False

    # Redis & Caching
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = Field(default=60, ge=1)

    # Security & JWT
    secret_key: str = DEFAULT_INSECURE_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)

    # Email notifications
    smtp_enabled: bool = False
    smtp_host: str = "localhost"
    smtp_port: int = Field(default=1025, ge=1, le=65535)
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@taskhub.local"

    @model_validator(mode="after")
    def validate_environment_security(self) -> "Settings":
        """Fail fast if production/staging uses insecure defaults."""
        if not self.database_url.strip():
            raise ValueError("DATABASE_URL must not be empty")
        if self.environment in {"production", "staging"}:
            if self.secret_key == DEFAULT_INSECURE_SECRET or len(self.secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY must be a strong secret (>= 32 chars) in staging/production"
                )
            if self.debug:
                raise ValueError("DEBUG must be false in staging/production")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
