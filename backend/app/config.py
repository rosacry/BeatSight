"""Application configuration module.

Loads settings from environment variables or .env file.
See .env.example for all available configuration options.
"""

from functools import lru_cache
from typing import List, Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env.

    All settings can be overridden via environment variables.
    Settings are cached after first load for performance.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra env vars
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    app_name: str = "BeatSight Backend"
    environment: Literal["development", "staging", "production", "testing"] = Field(
        default="development", alias="ENVIRONMENT"
    )
    debug: bool = Field(default=False, alias="DEBUG")
    api_prefix: str = "/api"

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    database_dsn: str = Field(
        default="postgresql+asyncpg://beatsight:beatsight@localhost:5432/beatsight",
        alias="DATABASE_DSN",
    )
    database_pool_size: int = Field(default=10, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=20, alias="DATABASE_MAX_OVERFLOW")
    database_pool_timeout: int = Field(default=30, alias="DATABASE_POOL_TIMEOUT")

    # -------------------------------------------------------------------------
    # Redis / Caching
    # -------------------------------------------------------------------------
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    cache_default_ttl: int = Field(default=3600, alias="CACHE_DEFAULT_TTL")

    # -------------------------------------------------------------------------
    # Authentication (JWT)
    # -------------------------------------------------------------------------
    jwt_secret_key: str = Field(
        default="CHANGE_ME_IN_PRODUCTION_USE_SECURE_RANDOM_VALUE",
        alias="JWT_SECRET_KEY",
    )
    
    def validate_production_secrets(self) -> list[str]:
        """Validate that production-critical secrets are properly set.
        
        Returns list of validation errors. Empty list means all good.
        Call this during app startup in production.
        """
        errors = []
        if self.is_production:
            if "CHANGE_ME" in self.jwt_secret_key:
                errors.append("CRITICAL: JWT_SECRET_KEY must be set to a secure random value in production!")
            if "CHANGE_ME" in self.modal_webhook_secret:
                errors.append("CRITICAL: MODAL_WEBHOOK_SECRET must be set to a secure random value in production!")
            if not self.stripe_webhook_secret and self.stripe_secret_key:
                errors.append("WARNING: STRIPE_WEBHOOK_SECRET should be set when Stripe is enabled")
        return errors
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expires_minutes: int = Field(
        default=30, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    refresh_token_expires_days: int = Field(
        default=7, alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS"
    )

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", alias="LOG_LEVEL"
    )
    logging_json: bool = Field(default=False, alias="LOGGING_JSON")
    log_file_path: Optional[str] = Field(default=None, alias="LOG_FILE_PATH")

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"],
        alias="CORS_ALLOWED_ORIGINS",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse comma-separated CORS origins from env var."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # -------------------------------------------------------------------------
    # File Storage
    # -------------------------------------------------------------------------
    storage_backend: Literal["local", "azure_blob", "s3"] = Field(
        default="local", alias="STORAGE_BACKEND"
    )
    storage_local_path: str = Field(default="./storage", alias="STORAGE_LOCAL_PATH")
    max_upload_size_mb: int = Field(default=100, alias="MAX_UPLOAD_SIZE_MB")

    # Azure Blob Storage
    azure_storage_connection_string: Optional[str] = Field(
        default=None, alias="AZURE_STORAGE_CONNECTION_STRING"
    )
    azure_storage_container: str = Field(
        default="beatsight", alias="AZURE_STORAGE_CONTAINER"
    )

    # AWS S3
    aws_access_key_id: Optional[str] = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(
        default=None, alias="AWS_SECRET_ACCESS_KEY"
    )
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    aws_s3_bucket: str = Field(default="beatsight", alias="AWS_S3_BUCKET")

    # -------------------------------------------------------------------------
    # AI Pipeline
    # -------------------------------------------------------------------------
    ai_pipeline_path: str = Field(default="../ai-pipeline", alias="AI_PIPELINE_PATH")
    ml_model_path: Optional[str] = Field(default=None, alias="ML_MODEL_PATH")
    use_ml_classifier: bool = Field(default=True, alias="USE_ML_CLASSIFIER")
    ai_gpu_device: int = Field(default=-1, alias="AI_GPU_DEVICE")
    ai_job_timeout_seconds: int = Field(default=600, alias="AI_JOB_TIMEOUT_SECONDS")
    ai_max_concurrent_jobs: int = Field(default=2, alias="AI_MAX_CONCURRENT_JOBS")
    
    # Worker authentication secret (for internal AI job workers)
    worker_secret: str = Field(
        default="CHANGE_ME_IN_PRODUCTION_WORKER_SECRET",
        alias="WORKER_SECRET",
        description="Shared secret for authenticating AI worker endpoints",
    )

    # -------------------------------------------------------------------------
    # Modal.com GPU Orchestration
    # -------------------------------------------------------------------------
    modal_enabled: bool = Field(default=False, alias="MODAL_ENABLED")
    modal_token_id: Optional[str] = Field(default=None, alias="MODAL_TOKEN_ID")
    modal_token_secret: Optional[str] = Field(default=None, alias="MODAL_TOKEN_SECRET")
    modal_app_name: str = Field(default="beatsight-ai", alias="MODAL_APP_NAME")
    modal_environment: str = Field(default="main", alias="MODAL_ENVIRONMENT")
    modal_webhook_secret: str = Field(
        default="CHANGE_ME_IN_PRODUCTION",
        alias="MODAL_WEBHOOK_SECRET",
        description="Shared secret for Modal webhook authentication",
    )

    # -------------------------------------------------------------------------
    # Rate Limiting
    # -------------------------------------------------------------------------
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_default: int = Field(default=60, alias="RATE_LIMIT_DEFAULT")
    rate_limit_ai_jobs: int = Field(default=10, alias="RATE_LIMIT_AI_JOBS")

    # -------------------------------------------------------------------------
    # External Services
    # -------------------------------------------------------------------------
    musicbrainz_app_name: str = Field(default="BeatSight", alias="MUSICBRAINZ_APP_NAME")
    musicbrainz_app_version: str = Field(
        default="1.0.0", alias="MUSICBRAINZ_APP_VERSION"
    )
    musicbrainz_contact_email: Optional[str] = Field(
        default=None, alias="MUSICBRAINZ_CONTACT_EMAIL"
    )
    sentry_dsn: Optional[str] = Field(default=None, alias="SENTRY_DSN")

    # -------------------------------------------------------------------------
    # Security
    # -------------------------------------------------------------------------
    trusted_proxy_headers: Literal["none", "x-forwarded-for", "cf-connecting-ip"] = (
        Field(default="none", alias="TRUSTED_PROXY_HEADERS")
    )
    csp_report_uri: Optional[str] = Field(default=None, alias="CSP_REPORT_URI")

    # -------------------------------------------------------------------------
    # Stripe (Payments)
    # -------------------------------------------------------------------------
    stripe_secret_key: Optional[str] = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_publishable_key: Optional[str] = Field(
        default=None, alias="STRIPE_PUBLISHABLE_KEY"
    )
    stripe_webhook_secret: Optional[str] = Field(
        default=None, alias="STRIPE_WEBHOOK_SECRET"
    )
    stripe_basic_monthly_price_id: Optional[str] = Field(
        default=None, alias="STRIPE_BASIC_MONTHLY_PRICE_ID"
    )
    stripe_basic_yearly_price_id: Optional[str] = Field(
        default=None, alias="STRIPE_BASIC_YEARLY_PRICE_ID"
    )
    stripe_pro_monthly_price_id: Optional[str] = Field(
        default=None, alias="STRIPE_PRO_MONTHLY_PRICE_ID"
    )
    stripe_pro_yearly_price_id: Optional[str] = Field(
        default=None, alias="STRIPE_PRO_YEARLY_PRICE_ID"
    )

    # -------------------------------------------------------------------------
    # Subscription Quotas & Pricing
    # -------------------------------------------------------------------------
    # Monthly AI transcription limits per tier
    quota_free_monthly: int = Field(default=5, alias="QUOTA_FREE_MONTHLY")
    quota_basic_monthly: int = Field(default=30, alias="QUOTA_BASIC_MONTHLY")
    quota_pro_monthly: int = Field(
        default=999999, alias="QUOTA_PRO_MONTHLY"
    )  # Unlimited

    # Pricing in cents (for display purposes, Stripe handles actual billing)
    price_basic_monthly_cents: int = Field(
        default=800, alias="PRICE_BASIC_MONTHLY"
    )  # $8
    price_basic_yearly_cents: int = Field(
        default=6400, alias="PRICE_BASIC_YEARLY"
    )  # $64 (2 months free)
    price_pro_monthly_cents: int = Field(default=1500, alias="PRICE_PRO_MONTHLY")  # $15
    price_pro_yearly_cents: int = Field(
        default=12000, alias="PRICE_PRO_YEARLY"
    )  # $120 (2 months free)

    # -------------------------------------------------------------------------
    # Notifications (E2-006)
    # -------------------------------------------------------------------------
    sendgrid_api_key: Optional[str] = Field(default=None, alias="SENDGRID_API_KEY")
    email_from: Optional[str] = Field(default=None, alias="EMAIL_FROM")
    vapid_private_key: Optional[str] = Field(default=None, alias="VAPID_PRIVATE_KEY")
    vapid_public_key: Optional[str] = Field(default=None, alias="VAPID_PUBLIC_KEY")
    frontend_url: Optional[str] = Field(default=None, alias="FRONTEND_URL")
    notification_rate_limit_per_hour: int = Field(
        default=10, alias="NOTIFICATION_RATE_LIMIT"
    )

    # -------------------------------------------------------------------------
    # Alerting (E6-003)
    # -------------------------------------------------------------------------
    slack_webhook_url: Optional[str] = Field(default=None, alias="SLACK_WEBHOOK_URL")
    discord_webhook_url: Optional[str] = Field(
        default=None, alias="DISCORD_WEBHOOK_URL"
    )
    pagerduty_routing_key: Optional[str] = Field(
        default=None, alias="PAGERDUTY_ROUTING_KEY"
    )

    # -------------------------------------------------------------------------
    # Feature Flags
    # -------------------------------------------------------------------------
    feature_community: bool = Field(default=True, alias="FEATURE_COMMUNITY")
    feature_karma: bool = Field(default=True, alias="FEATURE_KARMA")
    feature_cloud_sync: bool = Field(default=False, alias="FEATURE_CLOUD_SYNC")
    feature_beta: bool = Field(default=False, alias="FEATURE_BETA")

    # -------------------------------------------------------------------------
    # Computed Properties
    # -------------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    @property
    def max_upload_size_bytes(self) -> int:
        """Get max upload size in bytes."""
        return self.max_upload_size_mb * 1024 * 1024

    def validate_production_settings(self) -> list[str]:
        """Validate settings are safe for production.

        Returns a list of warnings/errors.
        """
        issues = []

        if self.is_production:
            if "CHANGE_ME" in self.jwt_secret_key:
                issues.append("JWT_SECRET_KEY must be changed in production!")
            if self.debug:
                issues.append("DEBUG should be False in production!")
            if "*" in self.cors_origins:
                issues.append("CORS_ALLOWED_ORIGINS should not use * in production!")
            if not self.sentry_dsn:
                issues.append("SENTRY_DSN recommended for production error tracking")

        return issues


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance.

    Settings are loaded once and cached for the lifetime of the application.
    To reload settings, restart the application.
    """
    return Settings()
