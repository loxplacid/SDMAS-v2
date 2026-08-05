"""ASGI middleware that automatically records every mutating HTTP request
(POST, PATCH, PUT, DELETE) to the audit log.

The middleware extracts:

* The authenticated actor from the JWT token (typed: user/platform)
* The request path, method, and status code
* The client IP address and User-Agent
* The campus_id from the tenant context (set by TenantContextMiddleware)
* The correlation/request id (from header or generated per request)
* The outcome (``result``) derived from the response status code

It does **not** attempt to parse request/response bodies for before/after
state --- that level of detail is left to domain-specific code that knows
the exact shape of the data.

Unauthenticated mutating requests (e.g. ``/auth/register``) are recorded
with an explicit ``SYSTEM`` actor labelled ``"unattributed"`` rather than a
fabricated user id.  Domain services that know the real actor (e.g. the
register endpoint records the newly created user) write their own, more
accurate entry.
"""

from __future__ import annotations

import logging
import time
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.security.client_ip import get_client_ip, get_client_scheme
from app.domains.audit.actors import ActorType, AuditActor
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

# Path segments that carry a semantic action distinct from the generic
# HTTP-method action.  The LAST matching segment wins (deepest specificity).
_SEMANTIC_ACTIONS = {
    "approve": "APPROVE",
    "reject": "REJECT",
    "verify": "VERIFY",
    "export": "EXPORT",
    "download": "DOWNLOAD",
    "publish": "PUBLISH",
    "archive": "ARCHIVE",
    "restore": "RESTORE",
    "refund": "REFUND",
    "read": "MARK_READ",
    "mark-all": "MARK_ALL_READ",
    "switch": "SWITCH_SCHOOL",
    "transition": "STUDENT_TRANSITION",
}


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
        "actor_type": None,
        "actor_id": None,
        "campus_id": None,
        "tenant_id": None,
        "ip_address": get_client_ip(request),
        "scheme": get_client_scheme(request),
        "user_agent": request.headers.get("user-agent"),
        "correlation_id": (
            request.headers.get("X-Correlation-ID")
            or request.headers.get("X-Request-ID")
        ),
    }

    # Try tenant context first (set by TenantContextMiddleware)
    tenant = getattr(request.state, "tenant", None)
    if tenant is not None:
        metadata["campus_id"] = tenant.campus_id
        metadata["tenant_id"] = tenant.institution_id

    # Try JWT token for user info
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ")
        try:
            payload = decode_token(token)
            user_id = int(payload["sub"])
            metadata["user_id"] = user_id
            metadata["username"] = payload.get("username")
            metadata["actor_type"] = ActorType.USER.value
            metadata["actor_id"] = str(user_id)
            if metadata["campus_id"] is None:
                metadata["campus_id"] = payload.get("campus_id")
        except (ValueError, KeyError, TypeError):
            logger.debug("Could not decode token for audit metadata")

    # Unauthenticated mutating request → explicit SYSTEM/unattributed
    # actor (truthful marker, never a fabricated human id).
    if metadata["actor_type"] is None:
        metadata["actor_type"] = ActorType.SYSTEM.value
        metadata["actor_id"] = "unattributed"

    return metadata


def _semantic_action(method: str, path: str) -> str:
    """Map a request to a meaningful semantic action when possible,
    falling back to the generic HTTP-method action."""
    for segment in reversed(path.split("/")):
        if not segment:
            continue
        action = _SEMANTIC_ACTIONS.get(segment.lower())
        if action:
            return action
    return (
        "CREATE" if method == "POST"
        else "DELETE" if method == "DELETE"
        else "UPDATE"
    )


def _result_for_status(status_code: int) -> tuple[str, str | None]:
    """Derive the audit outcome from the HTTP status code."""
    if 200 <= status_code < 300:
        return "SUCCESS", None
    if status_code == 401 or status_code == 403:
        return "FAILURE", f"HTTP {status_code} unauthorized"
    return "FAILURE", f"HTTP {status_code}"


def _build_actor(
    actor_type: str | None,
    actor_id: str | None,
    username: str | None,
) -> AuditActor:
    """Construct the typed :class:`AuditActor` for the middleware entry.

    Unauthenticated requests get the explicit SYSTEM actor labelled
    ``"unattributed"`` — never a fabricated human id.
    """
    if actor_type == ActorType.USER.value and actor_id and actor_id.isdigit():
        return AuditActor.user(user_id=int(actor_id), username=username)
    return AuditActor.system(reason="unattributed")


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
        "documents": "document",
        "billing": "billing",
        "reports": "report",
        "jobs": "job",
        "reconciliations": "reconciliation",
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
      (desirable for security) — recorded with ``result=FAILURE``.
    * A successful business transaction whose audit write fails will
      still succeed (audit is best-effort at the HTTP layer).

    Critical domain events (payments, verifications, approvals) are
    additionally recorded **in the same transaction** by their services,
    so those records are guaranteed to exist when the business action
    succeeds.
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

        action = _semantic_action(request.method, request.url.path)
        resource_type = _resource_type_from_path(request.url.path)
        result, failure_reason = _result_for_status(response.status_code)

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
            actor = _build_actor(
                actor_type=metadata["actor_type"],
                actor_id=metadata["actor_id"],
                username=metadata["username"],
            )
            await svc.record(
                actor=actor,
                user_id=metadata["user_id"],
                username=metadata["username"],
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "scheme": metadata.get("scheme"),
                },
                result=result,
                failure_reason=failure_reason,
                ip_address=metadata["ip_address"],
                user_agent=metadata["user_agent"],
                campus_id=metadata["campus_id"],
                tenant_id=metadata["tenant_id"],
                correlation_id=metadata["correlation_id"],
                commit=True,
            )
        except Exception:
            if audit_session is not None:
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
