from __future__ import annotations

import csv
import io
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class LegacyReader(ABC):
    """Abstract reader for legacy data sources."""

    @abstractmethod
    async def read_entity(self, entity_type: str) -> list[dict[str, Any]]:
        """Read all records for a given entity type."""

    @abstractmethod
    async def read_all(self) -> dict[str, list[dict[str, Any]]]:
        """Read all available entities. Returns {entity_type: [records]}."""

    @abstractmethod
    async def validate_source(self) -> list[str]:
        """Check the source is accessible. Returns list of issues (empty = OK)."""


class LegacyJSONReader(LegacyReader):
    """Reads legacy data from a JSON file or directory of JSON files.

    Expected formats:

    1. A single JSON file with top-level keys per entity::

        {
            "users": [...],
            "students": [...],
            "academic_years": [...],
            ...
        }

    2. A directory where each file is named ``{entity_type}.json``::

        /path/to/dump/
            users.json
            students.json
            academic_years.json
            ...

    3. A directory where each file is a JSON Lines (``.jsonl``) file
       with one record per line.

    This reader never silently modifies data — every field is read
    as-is and passed to the migration engine for validation.
    """

    def __init__(self, path: str) -> None:
        self._path = path

    async def read_entity(self, entity_type: str) -> list[dict[str, Any]]:
        records = await self._try_read_single_file(entity_type)
        if records is not None:
            return records

        combined = await self.read_all()
        return combined.get(entity_type, [])

    async def read_all(self) -> dict[str, list[dict[str, Any]]]:
        if os.path.isfile(self._path):
            return await self._read_single_file(self._path)

        if os.path.isdir(self._path):
            return await self._read_directory(self._path)

        raise FileNotFoundError(f"Legacy data source not found: {self._path}")

    async def validate_source(self) -> list[str]:
        issues: list[str] = []
        if not os.path.exists(self._path):
            issues.append(f"Path does not exist: {self._path}")
            return issues
        if os.path.isfile(self._path):
            try:
                async with _async_open(self._path) as f:
                    data = json.loads(await f.read())
                    if not isinstance(data, dict):
                        issues.append("Root JSON must be an object (entity_type -> records)")
            except json.JSONDecodeError as e:
                issues.append(f"Invalid JSON: {e}")
            except Exception as e:
                issues.append(f"Cannot read file: {e}")
        elif os.path.isdir(self._path):
            json_files = [
                f for f in os.listdir(self._path)
                if f.endswith((".json", ".jsonl"))
            ]
            if not json_files:
                issues.append(f"Directory '{self._path}' contains no .json or .jsonl files")
        return issues

    async def _try_read_single_file(
        self, entity_type: str
    ) -> list[dict[str, Any]] | None:
        if not os.path.isdir(self._path):
            return None
        json_path = os.path.join(self._path, f"{entity_type}.json")
        jsonl_path = os.path.join(self._path, f"{entity_type}.jsonl")
        csv_path = os.path.join(self._path, f"{entity_type}.csv")

        if os.path.isfile(json_path):
            data = await self._read_single_file(json_path)
            return data.get(entity_type, [])
        if os.path.isfile(jsonl_path):
            return await self._read_jsonl(jsonl_path)
        if os.path.isfile(csv_path):
            return await self._read_csv(csv_path)
        return None

    async def _read_single_file(
        self, path: str
    ) -> dict[str, list[dict[str, Any]]]:
        async with _async_open(path) as f:
            data = json.loads(await f.read())
        if isinstance(data, dict):
            return data
        raise ValueError(f"Expected JSON object at {path}, got {type(data).__name__}")

    async def _read_jsonl(self, path: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        async with _async_open(path) as f:
            for line in (await f.read()).strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.warning("Skipping invalid JSONL line in %s: %s", path, e)
        return records

    async def _read_csv(self, path: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        async with _async_open(path) as f:
            reader = csv.DictReader(io.StringIO(await f.read()))
            for row in reader:
                cleaned = {k.strip(): v.strip() if v else None for k, v in row.items()}
                records.append(cleaned)
        return records

    async def _read_directory(
        self, dir_path: str
    ) -> dict[str, list[dict[str, Any]]]:
        combined: dict[str, list[dict[str, Any]]] = {}
        for fname in sorted(os.listdir(dir_path)):
            fpath = os.path.join(dir_path, fname)
            if not os.path.isfile(fpath):
                continue
            if fname.endswith(".json") and not fname.endswith(".jsonl"):
                entity_type = fname[:-5]
                data = await self._read_single_file(fpath)
                if entity_type in data:
                    combined[entity_type] = data[entity_type]
                else:
                    logger.warning(
                        "Expected key '%s' in %s — found keys: %s",
                        entity_type, fname, list(data.keys()),
                    )
            elif fname.endswith(".jsonl"):
                entity_type = fname[:-6]
                combined[entity_type] = await self._read_jsonl(fpath)
            elif fname.endswith(".csv"):
                entity_type = fname[:-4]
                combined[entity_type] = await self._read_csv(fpath)
        return combined


class LegacyAPIReader(LegacyReader):
    """Reads legacy data from a REST API endpoint.

    The API is expected to return JSON like::

        GET /api/export/{entity_type}
        -> {"data": [record, ...], "total": N}

    Or::

        GET /api/export/all
        -> {entity_type: [record, ...], ...}
    """

    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    async def read_entity(self, entity_type: str) -> list[dict[str, Any]]:
        import httpx

        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        url = f"{self._base_url}/api/export/{entity_type}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=60.0)
            resp.raise_for_status()
            body = resp.json()
        return body.get("data", body)

    async def read_all(self) -> dict[str, list[dict[str, Any]]]:
        import httpx

        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        url = f"{self._base_url}/api/export/all"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=120.0)
            resp.raise_for_status()
            body = resp.json()
        return {k: v for k, v in body.items() if isinstance(v, list)}

    async def validate_source(self) -> list[str]:
        import httpx

        issues: list[str] = []
        try:
            headers = {}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._base_url}/api/export/health",
                    headers=headers,
                    timeout=10.0,
                )
            if resp.status_code >= 400:
                issues.append(f"API returned {resp.status_code}")
        except Exception as e:
            issues.append(f"Cannot reach API: {e}")
        return issues


def _async_open(path: str, mode: str = "r") -> Any:
    """Return an aiofiles async context manager for the given path.

    Callers use ``async with _async_open(path) as f: content = await f.read()``.
    This must be a plain function — not ``async def`` — so it returns the
    context manager object itself rather than a coroutine.  An ``async def``
    version would ``await aiofiles.open()`` (resolving to the already-open
    file handle) and callers doing ``async with _async_open(...)`` would
    receive a coroutine with no ``__aenter__``, raising ``AttributeError``.
    """
    import aiofiles

    return aiofiles.open(path, mode, encoding="utf-8")
