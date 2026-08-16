"""Distributed (Redis-backed) rate-limiter tests.

Proves the properties the audit requires of a multi-replica limiter:

* **replica-independent behavior** — two limiter instances sharing one
  store enforce a single combined window (what two API replicas do);
* **atomic counters / TTL / bounded memory** — INCR-based fixed window
  with a TTL armed by the first request, so keys expire;
* **consistent 429 semantics** — the same (allowed, retry_after) shape;
* **explicit failure mode** — fail-open (allow + log) by default,
  fail-closed (503) when ``RATE_LIMIT_FAIL_CLOSED`` is set.

No real Redis server is required: the store is a minimal in-memory fake
exposing the same async interface ``RedisRateLimiter`` relies on.
"""

from __future__ import annotations

import time

import pytest

from app.config import settings
from app.core.security.rate_limiter import RedisRateLimiter


class _FakeRedis:
    """Minimal async Redis-compatible fake (INCR/EXPIRE/TTL/DEL/SCAN)."""

    def __init__(self) -> None:
        self._store: dict[str, int] = {}
        self._ttl: dict[str, float] = {}  # key -> monotonic expiry

    def _expire_now(self) -> None:
        now = time.monotonic()
        for k in [k for k, exp in self._ttl.items() if exp <= now]:
            self._store.pop(k, None)
            self._ttl.pop(k, None)

    async def incr(self, key: str) -> int:
        self._expire_now()
        self._store[key] = self._store.get(key, 0) + 1
        return self._store[key]

    async def expire(self, key: str, seconds: int) -> bool:
        self._ttl[key] = time.monotonic() + seconds
        return True

    async def ttl(self, key: str) -> int:
        self._expire_now()
        if key not in self._store:
            return -2
        exp = self._ttl.get(key)
        if exp is None:
            return -1
        return max(int(exp - time.monotonic()), 0)

    async def delete(self, key: str) -> int:
        self._expire_now()
        return 1 if self._store.pop(key, None) is not None else 0

    async def scan_iter(self, match: str = "*"):
        self._expire_now()
        prefix = match[:-1]  # "rl:*" -> "rl:"
        for k in list(self._store):
            if k.startswith(prefix):
                yield k


@pytest.fixture
def store() -> _FakeRedis:
    return _FakeRedis()


@pytest.fixture
def replica_a(store: _FakeRedis) -> RedisRateLimiter:
    """Replica A — the shared store is the source of truth."""
    return RedisRateLimiter(store, key_prefix="rl")


@pytest.fixture
def replica_b(store: _FakeRedis) -> RedisRateLimiter:
    """Replica B — same store, different process object."""
    return RedisRateLimiter(store, key_prefix="rl")


async def test_limits_shared_across_replicas(replica_a, replica_b):
    """5 logins across two replicas exhaust one shared 5/min window."""
    for limiter in (replica_a, replica_a, replica_b, replica_b, replica_a):
        allowed, _ = await limiter.check("login:203.0.113.7", max_requests=5, window_seconds=60)
        assert allowed is True

    allowed, retry_after = await replica_b.check(
        "login:203.0.113.7", max_requests=5, window_seconds=60
    )
    assert allowed is False
    assert retry_after >= 1


async def test_windows_are_per_key(replica_a):
    await replica_a.check("login:1.1.1.1", max_requests=2, window_seconds=60)
    allowed, _ = await replica_a.check("login:2.2.2.2", max_requests=2, window_seconds=60)
    assert allowed is True


async def test_ttl_bounds_memory(replica_a):
    """Keys expire after the window — memory stays bounded."""
    await replica_a.check("login:9.9.9.9", max_requests=1, window_seconds=60)
    assert await replica_a._client.ttl("rl:login:9.9.9.9") > 0
    # Reset drops the key entirely.
    await replica_a.reset("login:9.9.9.9")
    assert await replica_a._client.ttl("rl:login:9.9.9.9") == -2


async def test_reset_all_clears_prefix(replica_a, replica_b, store):
    await replica_a.check("login:1.1.1.1", max_requests=1, window_seconds=60)
    await replica_b.check("login:2.2.2.2", max_requests=1, window_seconds=60)
    await replica_a.reset()
    remaining = [k async for k in store.scan_iter(match="rl:*")]
    assert remaining == []


async def test_fail_open_on_store_outage(monkeypatch):
    """Default: a store outage allows the request and logs a warning."""
    class _BrokenStore:
        async def incr(self, key):  # noqa: ARG002
            raise ConnectionError("redis down")

        async def expire(self, key, seconds):  # noqa: ARG002
            raise ConnectionError("redis down")

        async def ttl(self, key):  # noqa: ARG002
            raise ConnectionError("redis down")

    monkeypatch.setattr(settings, "rate_limit_fail_closed", False)
    limiter = RedisRateLimiter(_BrokenStore())
    allowed, retry_after = await limiter.check("login:x", max_requests=5, window_seconds=60)
    assert allowed is True
    assert retry_after == 0


async def test_fail_closed_on_store_outage(monkeypatch):
    """With RATE_LIMIT_FAIL_CLOSED=true, a store outage rejects (503)."""
    from fastapi import HTTPException

    class _BrokenStore:
        async def incr(self, key):  # noqa: ARG002
            raise ConnectionError("redis down")

        async def expire(self, key, seconds):  # noqa: ARG002
            raise ConnectionError("redis down")

        async def ttl(self, key):  # noqa: ARG002
            raise ConnectionError("redis down")

    monkeypatch.setattr(settings, "rate_limit_fail_closed", True)
    limiter = RedisRateLimiter(_BrokenStore())
    with pytest.raises(HTTPException) as excinfo:
        await limiter.check("login:x", max_requests=5, window_seconds=60)
    assert excinfo.value.status_code == 503


def test_factory_returns_memory_limiter_without_redis(monkeypatch):
    """No REDIS_URL → in-memory fallback (single-process dev)."""
    from app.core.security.rate_limiter import RateLimiter, get_rate_limiter

    monkeypatch.setattr(settings, "redis_url", None)
    limiter = get_rate_limiter()
    assert isinstance(limiter, RateLimiter)


# ---------------------------------------------------------------------------
# Endpoint-level Redis outage behaviour (the "Redis restart" scenario)
# ---------------------------------------------------------------------------


class _BrokenStore:
    """A Redis-compatible store that is completely unavailable."""

    async def incr(self, key):  # noqa: ARG002
        raise ConnectionError("redis down")

    async def expire(self, key, seconds):  # noqa: ARG002
        raise ConnectionError("redis down")

    async def ttl(self, key):  # noqa: ARG002
        raise ConnectionError("redis down")


async def _replace_login_limiter_with_broken_redis(monkeypatch) -> None:
    """Point the auth router's login limiter at a broken Redis store.

    ``_login_limiter`` is a module-level singleton in ``auth/router.py``;
    replacing it simulates a production process whose Redis backend went
    down after startup (the connection exists, the store is unreachable).
    """
    from app.core.security.rate_limiter import RedisRateLimiter
    from app.domains.auth import router as auth_router

    monkeypatch.setattr(
        auth_router, "_login_limiter", RedisRateLimiter(_BrokenStore())
    )


async def test_login_fails_open_when_redis_down(api_client, monkeypatch):
    """Default policy: a Redis outage must NOT take down login — the
    request proceeds (limiter allows) and never returns 500."""
    monkeypatch.setattr(settings, "rate_limit_fail_closed", False)
    await _replace_login_limiter_with_broken_redis(monkeypatch)

    # The seeded admin logs in successfully despite the broken store.
    resp = await api_client.post(
        "/auth/login",
        json={"login": "admin", "password": "AdminPass123!"},
    )
    assert resp.status_code == 200, resp.text


async def test_login_fails_closed_when_redis_down(api_client, monkeypatch):
    """With RATE_LIMIT_FAIL_CLOSED=true, a Redis outage rejects login
    with a deliberate 503 — never a 500."""
    monkeypatch.setattr(settings, "rate_limit_fail_closed", True)
    await _replace_login_limiter_with_broken_redis(monkeypatch)

    resp = await api_client.post(
        "/auth/login",
        json={"login": "admin", "password": "AdminPass123!"},
    )
    assert resp.status_code == 503, resp.text
    assert resp.json()["detail"]["fail_closed"] is True


async def test_login_other_endpoints_unaffected_by_limiter_outage(api_client, monkeypatch):
    """Only limiter-guarded paths depend on the store: an unguarded
    endpoint (e.g. ``/auth/me``) keeps working during a Redis outage."""
    monkeypatch.setattr(settings, "rate_limit_fail_closed", False)
    await _replace_login_limiter_with_broken_redis(monkeypatch)

    # Login succeeds (fail-open), then the authenticated identity works.
    resp = await api_client.post(
        "/auth/login",
        json={"login": "admin", "password": "AdminPass123!"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]

    resp = await api_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["username"] == "admin"
