"""In-memory sliding-window rate limiter.

Keeps per-key request timestamps in a ``defaultdict[list[float]]``.
Old entries are pruned on every check.  Not suitable for multi-worker
deployments without Redis, but fine for single-process development
and small-to-medium production instances.

For production with multiple workers, swap this for a Redis-backed
implementation (same ``RateLimiter`` interface).
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from fastapi import HTTPException, Request, Response, status

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


class RateLimiter:
    """Sliding-window rate limiter with configurable limits per key.

    Usage::

        limiter = RateLimiter()
        limiter.check("login:user:42", max_requests=5, window_seconds=60)
    """

    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def check(
        self,
        key: str,
        max_requests: int = 10,
        window_seconds: int = 60,
    ) -> tuple[bool, int]:
        """Check if *key* has exceeded the rate limit.

        Returns ``(is_allowed, retry_after_seconds)``.
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


# Singleton for app-wide use
_global_limiter = RateLimiter()


def rate_limit(
    key_prefix: str,
    max_requests: int = 10,
    window_seconds: int = 60,
    limiter: RateLimiter | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator that applies rate limiting to a FastAPI route handler.

    The ``key_prefix`` is combined with the client IP to form the
    rate-limiting key::

        @router.post("/login")
        @rate_limit("login", max_requests=5, window_seconds=60)
        async def login(...): ...

    When the limit is exceeded a 429 response is returned.

    Usage with ``Request``::

        The decorated function signature must accept a ``request``
        keyword argument (FastAPI injects it automatically when the
        function parameter is named ``request``).
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

            client_ip = req.client.host if req.client else "unknown"
            key = f"{key_prefix}:{client_ip}"
            effective_limiter = limiter or _global_limiter
            allowed, retry_after = effective_limiter.check(
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
