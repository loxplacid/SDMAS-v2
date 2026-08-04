from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_default_settings():
    settings = Settings()
    assert settings.app_name == "SDMAS API"
    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.api_host == "0.0.0.0"
    assert settings.api_port == 8000
    assert settings.log_level == "INFO"


def test_environment_variable_overrides():
    env_vars = {
        "APP_NAME": "Test API",
        "ENVIRONMENT": "production",
        "DEBUG": "true",
        "API_HOST": "127.0.0.1",
        "API_PORT": "9000",
        "LOG_LEVEL": "DEBUG",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        settings = Settings()
        assert settings.app_name == "Test API"
        assert settings.environment == "production"
        assert settings.debug is True
        assert settings.api_host == "127.0.0.1"
        assert settings.api_port == 9000
        assert settings.log_level == "DEBUG"


def test_invalid_port_raises():
    with patch.dict(os.environ, {"API_PORT": "99999"}, clear=True):
        with pytest.raises(ValidationError):
            Settings()


def test_database_url_default():
    settings = Settings()
    assert settings.database_url is not None


def test_database_url_override():
    url = "postgresql+asyncpg://user:pass@localhost:5432/sdmas"
    with patch.dict(os.environ, {"DATABASE_URL": url}, clear=True):
        settings = Settings()
        assert str(settings.database_url) == url


def test_settings_immutable():
    settings = Settings()
    with pytest.raises(ValidationError):
        settings.app_name = "Changed"


def test_partial_overrides():
    env_vars = {
        "ENVIRONMENT": "staging",
        "LOG_LEVEL": "WARNING",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        settings = Settings()
        assert settings.environment == "staging"
        assert settings.log_level == "WARNING"
        assert settings.app_name == "SDMAS API"
