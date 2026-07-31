"""ASGI middleware that automatically records every mutating HTTP request
(POST, PATCH, DELETE) to the audit log.

The middleware extracts:

* The authenticated user from the JWT token
* The request path, method, and status code
* The client IP address and User-Agent
* The campus_id from the tenant context (set by TenantContextMiddleware)

It does **not** attempt to parse request/response bodies for before/after
state --- that level of detail is left to domain-specific code that knows
the exact shape of the data.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.domains.auth.security import decode_token
from app.domains.audit.service import AuditService
from app.infrastructure.database import get_async_session_factory

logger = logging.getLogger(__name__)

# HTTP methods that mutate state and should be audited
_MUTATING_METHODS = frozenset({"POST", "PATCH", "PUT", "DELETE"})

# Path prefixes that should NOT be audited (internal / health / auth)
_SKIP_PREFIXES = (
    "/health",
    "/ready",
    "/auth/login",
    "/auth/refresh",
    "/api/admin/audit-logs",
    "/docs",
    "/openapi.json",
    "/redoc",
)


def _should_audit(request: Request) -> bool:
    """Decide whether a request should produce an audit entry."""
    if request.method not in _MUTATING_METHODS:
        return False
    path = request.url.path
    return not path.startswith(_SKIP_PREFIXES)


def _extract_audit_metadata(
    request: Request,
) -> dict:
    """Extract actor, tenant, and request metadata from the request."""
    metadata: dict = {
        "user_id": None,
        "username": None,
        "campus_id": None,
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }

    # Try tenant context first (set by TenantContextMiddleware)
    tenant = getattr(request.state, "tenant", None)
    if tenant is not None:
        metadata["campus_id"] = tenant.campus_id

    # Try JWT token for user info
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ")
        try:
            payload = decode_token(token)
            metadata["user_id"] = int(payload["sub"])
            metadata["username"] = payload.get("username")
            if metadata["campus_id"] is None:
                metadata["campus_id"] = payload.get("campus_id")
        except (ValueError, KeyError, TypeError):
            logger.debug("Could not decode token for audit metadata")

    return metadata


def _resource_type_from_path(path: str) -> str:
    """Infer a resource type name from the URL path.

    E.g. ``/students/123`` → ``student``, ``/fees/fee-types`` → ``fee_type``.
    """
    parts = [p for p in path.split("/") if p]
    if not parts:
        return "unknown"

    # Map common prefixes to singular resource names
    resource_map = {
        "students": "student",
        "teachers": "teacher",
        "academic": "academic",
        "attendance": "attendance",
        "fees": "fee",
        "institutions": "institution",
        "campuses": "campus",
        "schools": "school",
        "departments": "department",
        "programs": "program",
        "branches": "branch",
        "semesters": "semester",
        "notifications": "notification",
        "admissions": "admission",
        "workflow": "workflow",
        "leave": "leave",
        "users": "user",
        "auth": "auth",
    }

    first = parts[0].lower()
    return resource_map.get(first, first)


_MINIMAL_LATENCY_S = 0.05  # 50 ms — skip recording for sub-50ms ops


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware that records every mutating HTTP request to the audit
    log asynchronously.

    Audit entries are written in a *separate* database session to avoid
    coupling the audit trail to the success/failure of the main business
    transaction.  This means:

    * A failed business transaction will still have an audit entry
      (desirable for security).
    * A successful business transaction whose audit write fails will
      still succeed (audit is best-effort).
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        elapsed = time.monotonic() - start

        if not _should_audit(request):
            return response

        # Skip very fast requests that are unlikely to have modified data
        # (e.g. 404s from static file probes)
        if elapsed < _MINIMAL_LATENCY_S:
            return response

        metadata = _extract_audit_metadata(request)

        action = (
            "CREATE" if request.method == "POST"
            else "DELETE" if request.method == "DELETE"
            else "UPDATE"
        )
        resource_type = _resource_type_from_path(request.url.path)

        # Try to extract a resource ID from the path
        path_segments = [p for p in request.url.path.split("/") if p]
        resource_id = None
        for seg in path_segments:
            if seg.isdigit():
                resource_id = seg
                break

        # Write audit entry in a separate session (decoupled from the
        # main business transaction so a failed audit never breaks the
        # request).  We create the session explicitly to avoid any
        # interaction with the ``async with`` lifecycle of other sessions.
        factory = get_async_session_factory()
        audit_session = None
        try:
            audit_session = factory()
            svc = AuditService(audit_session)
            await svc.record(
                user_id=metadata["user_id"],
                username=metadata["username"],
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                },
                ip_address=metadata["ip_address"],
                user_agent=metadata["user_agent"],
                campus_id=metadata["campus_id"],
            )
            await audit_session.commit()
        except Exception:
            await audit_session.rollback()
            logger.warning("Failed to write audit entry (non-fatal)", exc_info=True)
        finally:
            if audit_session is not None:
                await audit_session.close()

        return response


def register_audit_middleware(app: FastAPI) -> None:
    """Register the audit middleware on a FastAPI application.

    Must be called **after** the tenant context middleware so that
    ``request.state.tenant`` is available.
    """
    app.add_middleware(AuditMiddleware)
    logger.debug("AuditMiddleware registered")
