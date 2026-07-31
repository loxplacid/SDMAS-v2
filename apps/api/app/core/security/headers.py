"""ASGI middleware that adds security-related HTTP headers to every response.

Headers added:

* ``X-Content-Type-Options: nosniff`` — prevent MIME type sniffing
* ``X-Frame-Options: DENY`` — prevent clickjacking
* ``X-XSS-Protection: 0`` — disable legacy XSS filter (inconsistent across
  browsers; modern browsers use CSP instead)
* ``Strict-Transport-Security`` — only in production (enforce HTTPS)
* ``Referrer-Policy: strict-origin-when-cross-origin`` — limit referrer leakage
* ``Permissions-Policy`` — restrict access to browser features (geolocation,
  camera, microphone, etc.)

The middleware does **not** set ``Content-Security-Policy`` because the
frontend imports many inline scripts and styles via Vite. CSP is better
handled at the reverse-proxy level (nginx / Cloudflare) where it can be
tuned without a code deploy.

This middleware is intentionally placed **last** in the middleware stack
so that downstream middleware and route handlers can still read/modify
response headers before they are sent.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every outgoing response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        self._apply_headers(response)
        return response

    def _apply_headers(self, response: Response) -> None:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "interest-cohort=(), browsing-topics=()"
        )

        if settings.is_production():
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Remove Server header if present (leaks server software info)
        if "server" in response.headers:
            del response.headers["server"]


def register_security_headers_middleware(app: FastAPI) -> None:
    """Register the security headers middleware on a FastAPI application.

    This should be added **after** CORS and other middleware so that
    the headers are applied to all responses.
    """
    app.add_middleware(SecurityHeadersMiddleware)
    logger.debug("SecurityHeadersMiddleware registered")
