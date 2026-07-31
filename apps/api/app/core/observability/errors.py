from __future__ import annotations

import logging
import sys
import traceback
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class ErrorTracker(Protocol):
    def capture_exception(
        self,
        exc: BaseException | None = None,
        *,
        context: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
        user: dict[str, Any] | None = None,
    ) -> str | None:
        ...

    def capture_message(
        self,
        message: str,
        *,
        level: str = "error",
        context: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
    ) -> str | None:
        ...


class NoOpErrorTracker:
    def capture_exception(
        self,
        exc: BaseException | None = None,
        *,
        context: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
        user: dict[str, Any] | None = None,
    ) -> str | None:
        return None

    def capture_message(
        self,
        message: str,
        *,
        level: str = "error",
        context: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
    ) -> str | None:
        return None


class LoggingErrorTracker:
    def capture_exception(
        self,
        exc: BaseException | None = None,
        *,
        context: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
        user: dict[str, Any] | None = None,
    ) -> str | None:
        if exc is None:
            exc = sys.exc_info()[1]
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)) if exc else ""
        logger.error(
            "Captured exception",
            extra={"exception": tb, "context": context, "tags": tags, "user": user},
        )
        return str(hash(tb))

    def capture_message(
        self,
        message: str,
        *,
        level: str = "error",
        context: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
    ) -> str | None:
        log_level = getattr(logging, level.upper(), logging.ERROR)
        logger.log(
            log_level,
            "Captured message: %s",
            message,
            extra={"context": context, "tags": tags},
        )
        return None


_error_tracker: ErrorTracker = NoOpErrorTracker()


def get_error_tracker() -> ErrorTracker:
    return _error_tracker


def set_error_tracker(tracker: ErrorTracker) -> None:
    global _error_tracker
    _error_tracker = tracker


def capture_exception(
    exc: BaseException | None = None,
    *,
    context: dict[str, Any] | None = None,
    tags: dict[str, str] | None = None,
    user: dict[str, Any] | None = None,
) -> str | None:
    return _error_tracker.capture_exception(
        exc, context=context, tags=tags, user=user
    )


def capture_message(
    message: str,
    *,
    level: str = "error",
    context: dict[str, Any] | None = None,
    tags: dict[str, str] | None = None,
) -> str | None:
    return _error_tracker.capture_message(
        message, level=level, context=context, tags=tags
    )
