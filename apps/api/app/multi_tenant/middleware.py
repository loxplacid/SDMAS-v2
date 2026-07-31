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
from app.multi_tenant.models import TenantContext

logger = logging.getLogger(__name__)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Middleware that injects the current tenant context into
    ``request.state.tenant``.

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

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ")
            try:
                payload = decode_token(token)
                campus_id = payload.get("campus_id")
                if campus_id is not None:
                    request.state.tenant = TenantContext(
                        campus_id=int(campus_id),
                    )
            except ValueError:
                # Token is invalid or expired --- that's fine; the
                # auth dependency will catch this later.  Leave
                # tenant as unscoped.
                logger.debug("Could not decode token for tenant context")

        response = await call_next(request)
        return response


def register_tenant_middleware(app: FastAPI) -> None:
    """Register the tenant context middleware on a FastAPI application.

    Called from ``app.main`` during startup.
    """
    app.add_middleware(TenantContextMiddleware)
    logger.debug("TenantContextMiddleware registered")
