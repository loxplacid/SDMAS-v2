from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from pydantic import SecretStr, ValidationError

from app.config import Settings


def test_default_settings():
    settings = Settings()
    assert settings.app_name == "SDMAS API"
    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.log_level == "INFO"
    assert settings.redis_url is None
    assert settings.jwt_algorithm == "HS256"
    assert settings.access_token_expire_minutes == 30
    assert settings.refresh_token_expire_days == 7
    assert "http://localhost:3000" in settings.cors_origins


def test_sqlite_url_valid():
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    assert str(settings.database_url) == "sqlite+aiosqlite:///:memory:"


def test_postgresql_url_valid():
    url = "postgresql+asyncpg://user:pass@localhost:5432/sdmas"
    settings = Settings(database_url=url)
    assert str(settings.database_url) == url


def test_invalid_database_url():
    with pytest.raises(ValidationError):
        Settings(database_url="mysql://user:pass@localhost/db")


def test_environment_validation():
    with pytest.raises(ValidationError):
        Settings(environment="invalid")


def test_valid_environments():
    for env in ("development", "staging", "production", "test"):
        settings = Settings(environment=env)
        assert settings.environment == env


def test_log_level_validation():
    with pytest.raises(ValidationError):
        Settings(log_level="TRACE")


def test_cors_origins_override():
    origins = ["https://app.example.com"]
    settings = Settings(cors_origins=origins)
    assert settings.cors_origins == origins


def test_jwt_secret_is_secret_str():
    settings = Settings()
    assert isinstance(settings.jwt_secret, SecretStr)
    # Ensure the value is not printed in repr
    assert "change-me" not in repr(settings.jwt_secret)


def test_secret_str_not_exposed():
    """The SecretStr should mask the value in string representations."""
    settings = Settings(jwt_secret=SecretStr("super-secret-value"))
    raw = settings.jwt_secret.get_secret_value()
    assert raw == "super-secret-value"
    assert "super-secret-value" not in str(settings.jwt_secret)


def test_environment_methods():
    dev = Settings(environment="development")
    assert dev.is_development() is True
    assert dev.is_production() is False
    assert dev.is_test() is False

    prod = Settings(environment="production")
    assert prod.is_production() is True
    assert prod.is_development() is False

    test_env = Settings(environment="test")
    assert test_env.is_test() is True


def test_env_file_override():
    env_vars = {
        "APP_NAME": "Test API",
        "ENVIRONMENT": "production",
        "DEBUG": "true",
        "DATABASE_URL": "postgresql+asyncpg://u:p@localhost/db",
        "JWT_SECRET": "prod-secret",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "15",
        "CORS_ORIGINS": '["https://prod.example.com"]',
    }
    with patch.dict(os.environ, env_vars, clear=True):
        settings = Settings()
        assert settings.app_name == "Test API"
        assert settings.environment == "production"
        assert settings.debug is True
        assert str(settings.database_url) == "postgresql+asyncpg://u:p@localhost/db"
        assert settings.jwt_secret.get_secret_value() == "prod-secret"
        assert settings.access_token_expire_minutes == 15
        assert settings.cors_origins == ["https://prod.example.com"]


def test_partial_override():
    env_vars = {"ENVIRONMENT": "staging", "LOG_LEVEL": "WARNING"}
    with patch.dict(os.environ, env_vars, clear=True):
        settings = Settings()
        assert settings.environment == "staging"
        assert settings.log_level == "WARNING"
        assert settings.app_name == "SDMAS API"


def test_database_echo_default():
    settings = Settings()
    assert settings.database_echo is None


def test_database_echo_from_env():
    with patch.dict(os.environ, {"DATABASE_ECHO": "true"}, clear=True):
        settings = Settings()
        assert settings.database_echo is True


def test_redis_url_optional():
    settings = Settings(redis_url="redis://localhost:6380/1")
    assert settings.redis_url == "redis://localhost:6380/1"

    settings = Settings()
    assert settings.redis_url is None