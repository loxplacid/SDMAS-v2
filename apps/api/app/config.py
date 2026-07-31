from __future__ import annotations

from typing import List

from pydantic import Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="SDMAS API")
    environment: str = Field(default="development")
    debug: bool = Field(default=False)

    database_url: PostgresDsn | str = Field(
        default="sqlite+aiosqlite:///./sdmas_dev.db"
    )
    database_echo: bool | None = Field(default=None)

    redis_url: str | None = Field(default=None)

    jwt_secret: SecretStr = Field(default=SecretStr("change-me"))
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)

    # ── SendGrid (Email Notifications) ────────────────────────────
    sendgrid_api_key: str = Field(
        default="",
        description="SendGrid API key for transactional email delivery",
    )
    email_from_address: str = Field(
        default="noreply@sdmas.app",
        description="Sender email address for outgoing notifications",
    )
    email_from_name: str = Field(
        default="SDMAS Notifications",
        description="Sender display name for outgoing notifications",
    )

    # ── Payment Provider (Razorpay) ──────────────────────────────────
    razorpay_key_id: str = Field(
        default="",
        description="Razorpay API Key ID for payment processing",
    )
    razorpay_key_secret: str = Field(
        default="",
        description="Razorpay API Key Secret for payment processing",
    )

    # ── Document Storage ───────────────────────────────────────────
    storage_backend: str = Field(
        default="local",
        description="Storage backend: 'local' or 's3'",
    )
    storage_root: str = Field(
        default="storage/documents",
        description="Root directory for local file storage",
    )
    s3_endpoint: str | None = Field(
        default=None,
        description="S3-compatible endpoint URL (e.g. https://s3.amazonaws.com)",
    )
    s3_access_key_id: str | None = Field(default=None)
    s3_secret_access_key: SecretStr | None = Field(default=None)
    s3_bucket_name: str | None = Field(default=None)
    s3_region: str = Field(default="us-east-1")
    s3_use_ssl: bool = Field(default=True)
    max_file_size_mb: int = Field(default=20)
    allowed_mime_types: list[str] = Field(
        default=[
            "application/pdf",
            "image/jpeg", "image/png", "image/gif", "image/webp",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/csv", "text/plain",
        ]
    )
    document_storage_secret: SecretStr = Field(
        default=SecretStr("change-me-doc-secret"),
        description="Secret key for signing document URLs",
    )

    log_level: str = Field(default="INFO")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"]
    )

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production", "test"}
        if v.lower() not in allowed:
            msg = f"environment must be one of {allowed}, got {v}"
            raise ValueError(msg)
        return v.lower()

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            msg = f"log_level must be one of {allowed}, got {v}"
            raise ValueError(msg)
        return v.upper()

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: PostgresDsn | str) -> PostgresDsn | str:
        url = str(v)
        valid_schemes = ("sqlite+aiosqlite", "postgresql+asyncpg")
        if not any(url.startswith(s) for s in valid_schemes):
            msg = f"database_url must start with one of {valid_schemes}, got {url}"
            raise ValueError(msg)
        return v

    def is_production(self) -> bool:
        return self.environment == "production"

    def is_development(self) -> bool:
        return self.environment == "development"

    def is_test(self) -> bool:
        return self.environment == "test"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()