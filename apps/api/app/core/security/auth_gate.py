"""Global default-deny authentication gate.

Enforces the system-wide invariant that **every private endpoint requires
a valid access token** — regardless of whether a router remembered to add
a ``Depends`` — by rejecting unauthenticated requests at the middleware
layer before they reach any route.

Public endpoints are an explicit, audited allowlist (health checks,
intentionally public auth endpoints, billing plan listing, and the
signature-verified payment webhook).  Everything else fails closed with
``401 Unauthorized``.

The gate is defense-in-depth: routers still apply their own
``require_authenticated_user`` / ``require_tenant_context`` /
``require_permission`` dependencies, but an accidentally unprotected
route can no longer be reached anonymously.

NOTE on middleware ordering: the gate is registered last so it runs
*outermost* (first on the request).  CORS preflight (``OPTIONS``) is
always allowed through so the browser can perform cross-origin checks.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.domains.auth.security import decode_token

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public endpoint allowlist — keep this list small and deliberate.
# ---------------------------------------------------------------------------

# Exact paths that are intentionally public.
_PUBLIC_EXACT = frozenset(
    {
        # Health / liveness / readiness / metrics
        "/health",
        "/ready",
        "/metrics",
        # Interactive docs (dev/staging only; disabled in production)
        "/docs",
        "/redoc",
        "/openapi.json",
        # Intentionally public authentication endpoints
        "/auth/register",
        "/auth/login",
        "/auth/refresh",
        # Public plan catalog
        "/billing/plans",
    }
)

# Path prefixes that are intentionally public.
_PUBLIC_PREFIXES = (
    "/billing/plans/",
    # Payment webhook: authenticated by provider signature verification
    "/billing/webhook/",
)


def is_public_path(path: str) -> bool:
    """Return True when the path is in the explicit public allowlist."""
    normalized = path.rstrip("/") or "/"
    if normalized in _PUBLIC_EXACT:
        return True
    return any(normalized.startswith(p) for p in _PUBLIC_PREFIXES)


class AuthGateMiddleware(BaseHTTPMiddleware):
    """Reject unauthenticated requests to every non-public path with 401."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # CORS preflight must always pass through to the CORS middleware.
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if is_public_path(path):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
            if token:
                try:
                    payload = decode_token(token)
                except ValueError:
                    logger.debug("Auth gate: rejected invalid token for %s", path)
                else:
                    # Only access tokens authenticate requests; a refresh
                    # token must not double as a bearer credential.
                    if payload.get("type") == "access" and payload.get("sub"):
                        request.state.authenticated_user_id = _to_int(payload.get("sub"))
                        return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={"detail": "Not authenticated"},
            headers={"WWW-Authenticate": "Bearer"},
        )


def _to_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def register_auth_gate(app: FastAPI) -> None:
    """Register the auth gate as the outermost middleware.

    Because ``app.add_middleware`` prepends, calling this LAST makes the
    gate run first on every request.
    """
    app.add_middleware(AuthGateMiddleware)
    logger.debug("AuthGateMiddleware registered")
