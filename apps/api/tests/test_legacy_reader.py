"""Regression tests for LegacyJSONReader._async_open and every reader path.

Covers the two bugs that were present before the fix:

  BUG-1  _async_open was ``async def`` and returned ``await aiofiles.open()``,
         i.e. the already-open file handle.  Callers used
         ``async with _async_open(...) as f:`` which tried to enter a
         coroutine (no ``__aenter__``) → ``AttributeError`` at runtime.

  BUG-2  All four callers did ``f.read()`` (synchronous) on an aiofiles
         handle.  aiofiles file objects require ``await f.read()``.
         Without the await, ``f.read()`` returns a coroutine object;
         ``json.loads(coroutine)`` raises ``TypeError`` and
         ``csv.DictReader(coroutine)`` silently produces no rows.

Every affected reader path is exercised end-to-end:
  - validate_source  (single JSON file, directory, missing path)
  - _read_single_file  (via read_all on a single file)
  - _read_jsonl        (via read_entity on a .jsonl file in a directory)
  - _read_csv          (via read_entity on a .csv file in a directory)
  - _read_directory    (via read_all on a mixed directory)
  - read_entity        (fallback path through read_all for a single file)
"""

from __future__ import annotations

import json
import os
from typing import Any

import pytest

from app.domains.migration.readers.legacy_db import LegacyJSONReader, _async_open


# ---------------------------------------------------------------------------
# _async_open contract
# ---------------------------------------------------------------------------


def test_async_open_is_not_a_coroutine(tmp_path):
    """_async_open must return a context manager, not a coroutine."""
    import inspect

    p = tmp_path / "x.txt"
    p.write_text("hello", encoding="utf-8")
    result = _async_open(str(p))
    # Must NOT be a coroutine — that was the original bug.
    assert not inspect.iscoroutine(result), (
        "_async_open returned a coroutine; callers cannot use it as "
        "``async with _async_open(...) as f:``"
    )
    # Must expose __aenter__ so ``async with`` works.
    assert hasattr(result, "__aenter__"), "_async_open result has no __aenter__"
    assert hasattr(result, "__aexit__"), "_async_open result has no __aexit__"


async def test_async_open_reads_content(tmp_path):
    """The context manager returned by _async_open must yield a readable handle."""
    p = tmp_path / "data.txt"
    p.write_text("hello world", encoding="utf-8")
    async with _async_open(str(p)) as f:
        content = await f.read()
    assert content == "hello world"


# ---------------------------------------------------------------------------
# validate_source
# ---------------------------------------------------------------------------


async def test_validate_source_missing_path(tmp_path):
    reader = LegacyJSONReader(str(tmp_path / "does_not_exist.json"))
    issues = await reader.validate_source()
    assert len(issues) == 1
    assert "does not exist" in issues[0]


async def test_validate_source_valid_json_file(tmp_path):
    p = tmp_path / "dump.json"
    p.write_text(json.dumps({"students": [{"id": 1}]}), encoding="utf-8")
    reader = LegacyJSONReader(str(p))
    issues = await reader.validate_source()
    assert issues == []


async def test_validate_source_invalid_json_file(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json {{", encoding="utf-8")
    reader = LegacyJSONReader(str(p))
    issues = await reader.validate_source()
    assert len(issues) == 1
    assert "Invalid JSON" in issues[0]


async def test_validate_source_json_array_root_is_error(tmp_path):
    """Root must be a JSON object, not an array."""
    p = tmp_path / "array.json"
    p.write_text(json.dumps([{"id": 1}]), encoding="utf-8")
    reader = LegacyJSONReader(str(p))
    issues = await reader.validate_source()
    assert any("object" in i for i in issues)


async def test_validate_source_empty_directory(tmp_path):
    reader = LegacyJSONReader(str(tmp_path))
    issues = await reader.validate_source()
    assert any("no .json or .jsonl" in i for i in issues)


async def test_validate_source_directory_with_json_files(tmp_path):
    (tmp_path / "students.json").write_text(
        json.dumps({"students": []}), encoding="utf-8"
    )
    reader = LegacyJSONReader(str(tmp_path))
    issues = await reader.validate_source()
    assert issues == []


# ---------------------------------------------------------------------------
# _read_single_file  (via read_all on a single JSON file)
# ---------------------------------------------------------------------------


async def test_read_all_single_json_file(tmp_path):
    payload: dict[str, Any] = {
        "students": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
        "teachers": [{"id": 10, "name": "Dr. Smith"}],
    }
    p = tmp_path / "dump.json"
    p.write_text(json.dumps(payload), encoding="utf-8")

    reader = LegacyJSONReader(str(p))
    result = await reader.read_all()

    assert result["students"] == payload["students"]
    assert result["teachers"] == payload["teachers"]


async def test_read_all_single_file_non_object_raises(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    reader = LegacyJSONReader(str(p))
    with pytest.raises(ValueError, match="Expected JSON object"):
        await reader.read_all()


# ---------------------------------------------------------------------------
# _read_jsonl  (via read_entity on a .jsonl file in a directory)
# ---------------------------------------------------------------------------


async def test_read_entity_jsonl(tmp_path):
    lines = [
        json.dumps({"id": 1, "name": "Alice"}),
        json.dumps({"id": 2, "name": "Bob"}),
        "",  # blank line — must be skipped
    ]
    (tmp_path / "students.jsonl").write_text("\n".join(lines), encoding="utf-8")

    reader = LegacyJSONReader(str(tmp_path))
    records = await reader.read_entity("students")

    assert len(records) == 2
    assert records[0]["name"] == "Alice"
    assert records[1]["name"] == "Bob"


async def test_read_jsonl_skips_invalid_lines(tmp_path, caplog):
    lines = [
        json.dumps({"id": 1}),
        "NOT VALID JSON {{",
        json.dumps({"id": 2}),
    ]
    (tmp_path / "items.jsonl").write_text("\n".join(lines), encoding="utf-8")

    reader = LegacyJSONReader(str(tmp_path))
    records = await reader.read_entity("items")

    # Invalid line is skipped, not raised.
    assert len(records) == 2
    assert records[0]["id"] == 1
    assert records[1]["id"] == 2


# ---------------------------------------------------------------------------
# _read_csv  (via read_entity on a .csv file in a directory)
# ---------------------------------------------------------------------------


async def test_read_entity_csv(tmp_path):
    csv_content = (
        "id,name,email\n"
        "1,Alice,alice@example.com\n"
        "2,Bob,\n"
    )
    (tmp_path / "students.csv").write_text(csv_content, encoding="utf-8")

    reader = LegacyJSONReader(str(tmp_path))
    records = await reader.read_entity("students")

    assert len(records) == 2
    assert records[0]["id"] == "1"
    assert records[0]["name"] == "Alice"
    assert records[0]["email"] == "alice@example.com"
    # Empty value → None
    assert records[1]["email"] is None


async def test_read_csv_strips_header_whitespace(tmp_path):
    csv_content = " id , name \n1,Alice\n"
    (tmp_path / "users.csv").write_text(csv_content, encoding="utf-8")

    reader = LegacyJSONReader(str(tmp_path))
    records = await reader.read_entity("users")

    assert "id" in records[0]
    assert "name" in records[0]


# ---------------------------------------------------------------------------
# _read_directory  (via read_all on a mixed directory)
# ---------------------------------------------------------------------------


async def test_read_all_directory_mixed_formats(tmp_path):
    # .json file
    (tmp_path / "teachers.json").write_text(
        json.dumps({"teachers": [{"id": 10}]}), encoding="utf-8"
    )
    # .jsonl file
    (tmp_path / "students.jsonl").write_text(
        json.dumps({"id": 1}) + "\n" + json.dumps({"id": 2}),
        encoding="utf-8",
    )
    # .csv file
    (tmp_path / "fees.csv").write_text("id,amount\n1,5000\n", encoding="utf-8")
    # non-data file — must be ignored
    (tmp_path / "README.txt").write_text("ignore me", encoding="utf-8")

    reader = LegacyJSONReader(str(tmp_path))
    result = await reader.read_all()

    assert result["teachers"] == [{"id": 10}]
    assert len(result["students"]) == 2
    assert result["fees"][0]["amount"] == "5000"
    assert "README" not in result


async def test_read_all_directory_json_key_mismatch_warns(tmp_path, caplog):
    """A .json file whose top-level key doesn't match the filename is warned."""
    (tmp_path / "students.json").write_text(
        json.dumps({"WRONG_KEY": [{"id": 1}]}), encoding="utf-8"
    )
    reader = LegacyJSONReader(str(tmp_path))
    import logging

    with caplog.at_level(logging.WARNING):
        result = await reader.read_all()

    # The mismatched key is not surfaced under "students".
    assert "students" not in result
    assert any("students" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# read_entity  (fallback path: single file, entity not in directory)
# ---------------------------------------------------------------------------


async def test_read_entity_from_single_file(tmp_path):
    payload = {"users": [{"id": 99}], "students": [{"id": 1}, {"id": 2}]}
    p = tmp_path / "export.json"
    p.write_text(json.dumps(payload), encoding="utf-8")

    reader = LegacyJSONReader(str(p))
    records = await reader.read_entity("students")

    assert len(records) == 2
    assert records[0]["id"] == 1


async def test_read_entity_missing_returns_empty(tmp_path):
    payload = {"students": [{"id": 1}]}
    p = tmp_path / "export.json"
    p.write_text(json.dumps(payload), encoding="utf-8")

    reader = LegacyJSONReader(str(p))
    records = await reader.read_entity("teachers")

    assert records == []


async def test_read_all_missing_path_raises(tmp_path):
    reader = LegacyJSONReader(str(tmp_path / "ghost"))
    with pytest.raises(FileNotFoundError):
        await reader.read_all()


# ---------------------------------------------------------------------------
# Unicode content round-trip
# ---------------------------------------------------------------------------


async def test_unicode_content_roundtrip(tmp_path):
    payload = {"students": [{"name": "Élodie Müller"}, {"name": "José García"}]}
    p = tmp_path / "unicode.json"
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    reader = LegacyJSONReader(str(p))
    records = await reader.read_entity("students")

    assert records[0]["name"] == "Élodie Müller"
    assert records[1]["name"] == "José García"


# ---------------------------------------------------------------------------
# Large file: streaming does not truncate
# ---------------------------------------------------------------------------


async def test_large_jsonl_reads_all_records(tmp_path):
    count = 5_000
    lines = [json.dumps({"id": i, "name": f"Student {i}"}) for i in range(count)]
    (tmp_path / "students.jsonl").write_text("\n".join(lines), encoding="utf-8")

    reader = LegacyJSONReader(str(tmp_path))
    records = await reader.read_entity("students")

    assert len(records) == count
    assert records[-1]["id"] == count - 1
