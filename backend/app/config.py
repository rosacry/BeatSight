"""Application configuration module."""

from functools import lru_cache
from typing import List

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = "BeatSight Backend"
    environment: str = Field(default="development", alias="ENVIRONMENT")
    api_prefix: str = "/api"
    cors_origins: List[AnyUrl | str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"])

    database_dsn: str = Field(
        default="postgresql+asyncpg://beatsight:beatsight@localhost:5432/beatsight",
        alias="DATABASE_DSN",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    access_token_expires_minutes: int = Field(default=60 * 24)
    refresh_token_expires_days: int = Field(default=30)

    logging_json: bool = Field(default=False, alias="LOGGING_JSON")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
