from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SecretsBackend(ABC):
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any: ...

    @abstractmethod
    def get_bulk(self, *keys: str) -> dict[str, Any]: ...


class EnvVarBackend(SecretsBackend):
    def get(self, key: str, default: Any = None) -> Any:
        return os.environ.get(key, default)

    def get_bulk(self, *keys: str) -> dict[str, Any]:
        return {k: os.environ.get(k) for k in keys}


class EnvFileBackend(SecretsBackend):
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._vars: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            logger.warning("Env file not found: %s", self.path)
            return
        for line in self.path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            self._vars[key.strip()] = value.strip().strip("\"'")

    def get(self, key: str, default: Any = None) -> Any:
        return self._vars.get(key, default)

    def get_bulk(self, *keys: str) -> dict[str, Any]:
        return {k: self._vars.get(k) for k in keys}


class DockerSecretBackend(SecretsBackend):
    def __init__(self, secrets_dir: str | Path = "/run/secrets"):
        self.secrets_dir = Path(secrets_dir)

    def get(self, key: str, default: Any = None) -> Any:
        secret_path = self.secrets_dir / key
        if secret_path.exists():
            return secret_path.read_text().strip()
        return default

    def get_bulk(self, *keys: str) -> dict[str, Any]:
        return {k: self.get(k) for k in keys}


class VaultBackend(SecretsBackend):
    def __init__(
        self,
        url: str,
        token: str,
        mount_path: str = "secret",
        engine_version: int = 2,
    ):
        self.url = url.rstrip("/")
        self.token = token
        self.mount_path = mount_path
        self.engine_version = engine_version
        self._client: Any = None
        self._cache: dict[str, dict[str, Any]] = {}

    def _lazy_init(self):
        if self._client is not None:
            return
        try:
            import hvac

            self._client = hvac.Client(url=self.url, token=self.token)
        except ImportError:
            logger.error("hvac not installed; cannot use Vault backend")
            raise

    def get(self, key: str, default: Any = None) -> Any:
        self._lazy_init()
        path, _, field = key.partition(".")
        if path not in self._cache:
            try:
                secret = self._client.secrets.kv.v2.read_secret_version(
                    path=path, mount_point=self.mount_path
                )
                self._cache[path] = secret["data"]["data"]
            except Exception:
                return default
        return self._cache[path].get(field, default)

    def get_bulk(self, *keys: str) -> dict[str, Any]:
        return {k: self.get(k) for k in keys}


class SecretsManager:
    def __init__(self, backends: list[SecretsBackend] | None = None):
        self.backends = backends or [EnvVarBackend()]

    def get(self, key: str, default: Any = None) -> Any:
        for backend in self.backends:
            value = backend.get(key)
            if value is not None:
                return value
        return default

    def get_int(self, key: str, default: int | None = None) -> int | None:
        value = self.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool | None = None) -> bool | None:
        value = self.get(key)
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return value.lower() in ("true", "1", "yes", "on")

    def get_json(self, key: str, default: Any = None) -> Any:
        value = self.get(key)
        if value is None:
            return default
        if isinstance(value, dict):
            return value
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default

    def get_bulk(self, *keys: str) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for backend in self.backends:
            remaining = [k for k in keys if k not in result]
            if not remaining:
                break
            result.update(backend.get_bulk(*remaining))
        return result

    @classmethod
    def from_settings(cls, env_file: str | Path | None = None) -> SecretsManager:
        backends: list[SecretsBackend] = [EnvVarBackend()]
        if env_file and Path(env_file).exists():
            backends.append(EnvFileBackend(env_file))
        docker_secrets = Path("/run/secrets")
        if docker_secrets.exists():
            backends.append(DockerSecretBackend())
        return cls(backends=backends)


_secrets_manager: SecretsManager | None = None


def get_secrets() -> SecretsManager:
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager.from_settings()
    return _secrets_manager


def configure_secrets(env_file: str | Path | None = None) -> SecretsManager:
    global _secrets_manager
    _secrets_manager = SecretsManager.from_settings(env_file=env_file)
    return _secrets_manager
