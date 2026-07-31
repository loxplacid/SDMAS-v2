from __future__ import annotations

import json
import logging
import sys
import traceback
from collections.abc import MutableMapping
from typing import Any

from app.core.observability.middleware import current_request_context

_LOG_RECORD_BUILTIN_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)

_RESERVED_ATTRS = _LOG_RECORD_BUILTIN_ATTRS | {"timestamp", "logger", "severity", "exception"}


class JSONFormatter(logging.Formatter):
    def __init__(
        self,
        *,
        pretty: bool = False,
        indent: int | None = None,
    ) -> None:
        super().__init__()
        self._pretty = pretty
        self._indent = indent

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        ctx = current_request_context()
        if ctx is not None:
            log_data["request_id"] = ctx.get("request_id")
            log_data["correlation_id"] = ctx.get("correlation_id")

        if record.exc_info and record.exc_info[0] is not None:
            tb = traceback.format_exception(*record.exc_info)
            log_data["exception"] = "".join(tb)

        for key, value in record.__dict__.items():
            if key.startswith("_") or key in _RESERVED_ATTRS:
                continue
            log_data[key] = value

        kwargs: dict[str, Any] = {"ensure_ascii": False}
        if self._pretty or self._indent is not None:
            kwargs["indent"] = self._indent or 2
        return json.dumps(log_data, **kwargs)


def configure_json_logging(
    level: str = "INFO",
    *,
    pretty: bool = False,
    indent: int | None = None,
) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter(pretty=pretty, indent=indent))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.handlers.clear()
    uvicorn_logger.propagate = True
