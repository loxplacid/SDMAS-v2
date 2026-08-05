"""Rate limiting: in-memory (dev/single-process) and Redis-backed
(distributed, production).

Two implementations share one interface (``check`` / ``reset``):

* :class:`RateLimiter` — in-memory sliding window.  Fine for single-process
  development; NOT shared across API replicas.
* :class:`RedisRateLimiter` — fixed window over an atomic ``INCR`` +
  ``TTL``.  Shared across every replica (replica-independent limits),
  with bounded memory (keys expire after the window) and consistent
  429 semantics.

:func:`get_rate_limiter` returns the Redis-backed limiter when
``REDIS_URL`` is configured and the in-memory fallback otherwise.

Failure behaviour is **explicit**:

* default **fail-open** — a Redis outage lets the request through and logs
  a warning (availability first; rate limiting degrades, the app does not);
* ``RATE_LIMIT_FAIL_CLOSED=true`` flips to **fail-closed** — a Redis
  outage rejects protected requests with HTTP 503 (strictness first;
  an operator accepts that a limiter-store outage blocks the endpoints
  it guards).
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from fastapi import HTTPException, Request, Response, status

from app.config import settings
from app.core.security.client_ip import get_client_ip

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


class RateLimiter:
    """In-memory sliding-window rate limiter with configurable limits per key.

    Usage::

        limiter = RateLimiter()
        limiter.check("login:user:42", max_requests=5, window_seconds=60)
    """

    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = defaultdict(list)

    async def check(
        self,
        key: str,
        max_requests: int = 10,
        window_seconds: int = 60,
    ) -> tuple[bool, int]:
        """Check if *key* has exceeded the rate limit.

        Returns ``(is_allowed, retry_after_seconds)``.  Async so both
        implementations share one interface.
        """
        now = time.monotonic()
        window_start = now - window_seconds

        timestamps = self._buckets[key]
        # Prune expired entries
        self._buckets[key] = [t for t in timestamps if t > window_start]
        pruned = self._buckets[key]

        if len(pruned) >= max_requests:
            oldest = pruned[0]
            retry_after = int(window_seconds - (now - oldest))
            logger.debug("Rate limit hit for '%s': %d/%d", key, len(pruned), max_requests)
            return False, max(retry_after, 1)

        pruned.append(now)
        return True, 0

    def reset(self, key: str | None = None) -> None:
        """Clear rate-limit state.

        With no argument, clears every bucket (useful between tests so a
        full suite run never trips shared-IP windows).  With ``key``,
        clears only that bucket.
        """
        if key is None:
            self._buckets.clear()
        else:
            self._buckets.pop(key, None)


class RedisRateLimiter:
    """Distributed fixed-window rate limiter backed by Redis.

    Uses an atomic ``INCR`` plus ``EXPIRE`` (set only by the request that
    opens the window), so concurrent replicas share one counter and the
    memory footprint is bounded by the key TTL.  Implements the same
    interface as :class:`RateLimiter`.

    ``client`` must be a ``redis.asyncio.Redis`` instance (any interface
    exposing ``incr``/``expire``/``ttl``/``delete``/``scan_iter`` works,
    which is what the unit tests rely on).
    """

    def __init__(self, client: object, key_prefix: str = "rl") -> None:
        self._client = client
        self._prefix = key_prefix

    def _key(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    async def check(
        self,
        key: str,
        max_requests: int = 10,
        window_seconds: int = 60,
    ) -> tuple[bool, int]:
        """Check *key* atomically across all replicas.

        Returns ``(is_allowed, retry_after_seconds)``.  On a store outage
        the behaviour is governed by ``settings.rate_limit_fail_closed``:
        fail-open → ``(True, 0)`` with a warning; fail-closed → HTTP 503.
        """
        rk = self._key(key)
        try:
            count = await self._client.incr(rk)
            if count == 1:
                # First request of the window: (re)arm the TTL.  INCR is
                # atomic, so the window is consistent across replicas.
                await self._client.expire(rk, window_seconds)
            if count <= max_requests:
                return True, 0
            ttl = await self._client.ttl(rk)
            return False, max(int(ttl or window_seconds), 1)
        except Exception:
            return await self._handle_store_unavailable(key)

    async def _handle_store_unavailable(self, key: str) -> tuple[bool, int]:
        if settings.rate_limit_fail_closed:
            logger.critical(
                "Redis rate-limit store unavailable — FAILING CLOSED "
                "(RATE_LIMIT_FAIL_CLOSED=true) for key '%s'",
                key,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "Rate-limit store unavailable",
                    "fail_closed": True,
                },
            )
        logger.warning(
            "Redis rate-limit store unavailable — FAILING OPEN (allowed) "
            "for key '%s'. Set RATE_LIMIT_FAIL_CLOSED=true to reject instead.",
            key,
        )
        return True, 0

    async def reset(self, key: str | None = None) -> None:
        """Clear rate-limit state for *key*, or the whole prefix."""
        try:
            if key is None:
                prefix = f"{self._prefix}:*"
                async for k in self._client.scan_iter(match=prefix):
                    await self._client.delete(k)
            else:
                await self._client.delete(self._key(key))
        except Exception:
            logger.warning("Redis rate-limit reset failed (non-fatal)", exc_info=True)


# ---------------------------------------------------------------------------
# App-wide limiter resolution
# ---------------------------------------------------------------------------

#: In-memory fallback for single-process development / tests.
_global_limiter = RateLimiter()

#: Lazily-constructed Redis-backed limiter (one per process, shared store).
_redis_limiter: RedisRateLimiter | None = None


def get_rate_limiter() -> RateLimiter | RedisRateLimiter:
    """Return the app-wide rate limiter.

    Redis-backed when ``REDIS_URL`` is configured (production: shared
    across all API replicas), otherwise the in-memory fallback.  Callers
    should treat the result as an opaque ``check``/``reset`` object.
    """
    if not settings.redis_url:
        return _global_limiter

    global _redis_limiter
    if _redis_limiter is None:
        from redis.asyncio import Redis

        client = Redis.from_url(settings.redis_url, decode_responses=True)
        _redis_limiter = RedisRateLimiter(client)
        logger.info("Rate limiting backed by Redis at %s", settings.redis_url)
    return _redis_limiter


def rate_limit(
    key_prefix: str,
    max_requests: int = 10,
    window_seconds: int = 60,
    limiter: RateLimiter | RedisRateLimiter | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator that applies rate limiting to a FastAPI route handler.

    The ``key_prefix`` is combined with the resolved client IP (through
    the trusted-proxy boundary) to form the rate-limiting key::

        @router.post("/login")
        @rate_limit("login", max_requests=5, window_seconds=60)
        async def login(...): ...

    When the limit is exceeded a 429 response is returned.  The decorated
    function signature must accept a ``request`` keyword argument (FastAPI
    injects it automatically when the parameter is named ``request``).

    The limiter is resolved through :func:`get_rate_limiter` (Redis-backed
    in production, in-memory in dev) unless an explicit ``limiter`` is
    supplied.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            req: Request | None = kwargs.get("request")
            if req is None:
                for arg in args:
                    if isinstance(arg, Request):
                        req = arg
                        break
            if req is None:
                return await func(*args, **kwargs)

            # Resolve the real client IP through the trusted-proxy boundary
            # so a forged X-Forwarded-For cannot rotate the rate-limit key.
            client_ip = get_client_ip(req) or "unknown"
            key = f"{key_prefix}:{client_ip}"
            effective_limiter = limiter or get_rate_limiter()
            allowed, retry_after = await effective_limiter.check(
                key,
                max_requests=max_requests,
                window_seconds=window_seconds,
            )
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Too many requests",
                        "retry_after_seconds": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )
            return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
