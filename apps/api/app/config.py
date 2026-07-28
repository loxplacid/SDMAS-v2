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