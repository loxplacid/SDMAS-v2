"""Security-specific audit logging helpers.

Provides structured logging for security events (failed logins,
permission denials, token reuse, rate-limit hits) that are separate
from the general-purpose audit middleware.

In production, these events should also be forwarded to a SIEM
or dedicated security monitoring pipeline.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("sdmas.security")


class SecurityAuditLogger:
    """Structured security event logger.

    All events are logged at ``WARNING`` level so they stand out
    in standard log aggregation.
    """

    SEVERITY_INFO = "info"
    SEVERITY_WARN = "warn"
    SEVERITY_CRIT = "crit"

    @staticmethod
    def _log(
        event: str,
        severity: str = SEVERITY_WARN,
        **context: Any,
    ) -> None:
        logger.warning(
            "SECURITY [%s] %s  %s",
            severity.upper(),
            event,
            "  ".join(f"{k}={v}" for k, v in context.items()),
        )

    @classmethod
    def login_failed(
        cls,
        username: str | None = None,
        ip_address: str | None = None,
        reason: str = "invalid_credentials",
        **extra: Any,
    ) -> None:
        """Record a failed login attempt."""
        cls._log(
            "LOGIN_FAILED",
            severity=cls.SEVERITY_WARN,
            username=username or "unknown",
            ip=ip_address or "unknown",
            reason=reason,
            **extra,
        )

    @classmethod
    def login_success(
        cls,
        user_id: int,
        username: str,
        ip_address: str | None = None,
        **extra: Any,
    ) -> None:
        """Record a successful login."""
        cls._log(
            "LOGIN_SUCCESS",
            severity=cls.SEVERITY_INFO,
            user_id=user_id,
            username=username,
            ip=ip_address or "unknown",
            **extra,
        )

    @classmethod
    def token_reuse_detected(
        cls,
        user_id: int,
        token_type: str = "refresh",
        **extra: Any,
    ) -> None:
        """Record a detected token reuse (potential token theft).

        This is a critical security event and should trigger
        additional investigation.
        """
        cls._log(
            "TOKEN_REUSE",
            severity=cls.SEVERITY_CRIT,
            user_id=user_id,
            token_type=token_type,
            **extra,
        )

    @classmethod
    def permission_denied(
        cls,
        user_id: int,
        username: str,
        required_permission: str,
        path: str | None = None,
        **extra: Any,
    ) -> None:
        """Record an authorization failure."""
        cls._log(
            "PERMISSION_DENIED",
            severity=cls.SEVERITY_WARN,
            user_id=user_id,
            username=username,
            permission=required_permission,
            path=path or "unknown",
            **extra,
        )

    @classmethod
    def rate_limit_hit(
        cls,
        key: str,
        ip_address: str | None = None,
        path: str | None = None,
        **extra: Any,
    ) -> None:
        """Record a rate-limit violation."""
        cls._log(
            "RATE_LIMIT",
            severity=cls.SEVERITY_WARN,
            key=key,
            ip=ip_address or "unknown",
            path=path or "unknown",
            **extra,
        )
