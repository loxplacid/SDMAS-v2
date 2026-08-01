"""ASGI middleware that attaches the resolved tenant context to every
authenticated request so downstream middleware and handlers can inspect
``request.state.tenant`` without re-resolving it.

The middleware is intentionally lazy --- tenant context is only resolved
once and then cached on ``request.state`` for the lifetime of the request.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.domains.auth.security import decode_token
from app.domains.events.base import new_correlation_id
from app.domains.events.context import event_context
from app.multi_tenant.models import TenantContext

logger = logging.getLogger(__name__)


def _claim_int(payload: dict, key: str) -> int | None:
    """Return an int claim from a JWT payload, or None when absent/invalid."""
    value = payload.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Middleware that injects the current tenant context into
    ``request.state.tenant`` and propagates the event context
    (tenant, actor, correlation) to domain events published during
    the request.

    The middleware decodes the JWT ``Authorization`` header to extract
    the ``campus_id`` claim without requiring a database lookup.  If
    the token is invalid, expired, or carries no ``campus_id``, the
    tenant is set to ``TenantContext()`` (unscoped), preserving
    backward compatibility.

    Route handlers should prefer the explicit ``get_current_tenant``
    FastAPI dependency over ``request.state.tenant`` when they need
    the tenant context.  This middleware is primarily a convenience
    for middleware-level code.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.state.tenant = TenantContext()

        school_id: int | None = None
        actor_user_id: int | None = None

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ")
            try:
                payload = decode_token(token)
                campus_id = _claim_int(payload, "campus_id")
                if campus_id is not None:
                    request.state.tenant = TenantContext(campus_id=campus_id)
                    school_id = campus_id
                actor_user_id = _claim_int(payload, "sub")
            except ValueError:
                # Token is invalid or expired --- that's fine; the
                # auth dependency will catch this later.  Leave
                # tenant as unscoped.
                logger.debug("Could not decode token for tenant context")

        # Propagate tenant/actor/correlation to domain events published
        # during this request so emitted events carry correct envelope data
        # without each router having to thread the context manually.  When
        # the client does not supply a correlation id, generate one per
        # request so every event published inside the request shares it.
        correlation_id = request.headers.get("X-Correlation-ID") or new_correlation_id()
        with event_context(
            correlation_id=correlation_id,
            actor_user_id=actor_user_id,
            school_id=school_id,
        ):
            response = await call_next(request)
        return response


def register_tenant_middleware(app: FastAPI) -> None:
    """Register the tenant context middleware on a FastAPI application.

    Called from ``app.main`` during startup.
    """
    app.add_middleware(TenantContextMiddleware)
    logger.debug("TenantContextMiddleware registered")
