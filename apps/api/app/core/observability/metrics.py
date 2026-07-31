from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Protocol


class MetricsBackend(Protocol):
    def counter(
        self,
        name: str,
        value: float = 1,
        tags: dict[str, str] | None = None,
    ) -> None:
        ...

    def histogram(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        ...

    def gauge(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        ...

    def timing(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        ...


class InMemoryMetricsBackend:
    def __init__(self) -> None:
        self._counters: dict[str, float] = defaultdict(float)
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._gauges: dict[str, float] = {}

    def counter(
        self,
        name: str,
        value: float = 1,
        tags: dict[str, str] | None = None,
    ) -> None:
        key = _key(name, tags)
        self._counters[key] += value

    def histogram(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        key = _key(name, tags)
        self._histograms[key].append(value)

    def gauge(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        key = _key(name, tags)
        self._gauges[key] = value

    def timing(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        self.histogram(name, value, tags=tags)

    def snapshot(self) -> dict[str, Any]:
        hist_summary: dict[str, dict[str, float]] = {}
        for key, vals in self._histograms.items():
            if not vals:
                continue
            sorted_vals = sorted(vals)
            n = len(sorted_vals)
            hist_summary[key] = {
                "count": n,
                "min": sorted_vals[0],
                "max": sorted_vals[-1],
                "avg": sum(sorted_vals) / n,
                "p50": sorted_vals[n // 2],
                "p95": sorted_vals[int(n * 0.95)],
                "p99": sorted_vals[int(n * 0.99)],
            }
        return {
            "counters": dict(self._counters),
            "histograms": hist_summary,
            "gauges": dict(self._gauges),
        }


class LoggingMetricsBackend:
    def __init__(self, logger_name: str = "sdmas.metrics") -> None:
        import logging
        self._logger = logging.getLogger(logger_name)

    def counter(
        self,
        name: str,
        value: float = 1,
        tags: dict[str, str] | None = None,
    ) -> None:
        self._logger.info("METRIC counter %s %s  %s", name, value, tags or {})

    def histogram(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        self._logger.info("METRIC histogram %s %s  %s", name, value, tags or {})

    def gauge(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        self._logger.info("METRIC gauge %s %s  %s", name, value, tags or {})

    def timing(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        self.histogram(name, value, tags=tags)


def _key(name: str, tags: dict[str, str] | None) -> str:
    if not tags:
        return name
    tag_parts = sorted(f"{k}={v}" for k, v in tags.items())
    return f"{name}#{','.join(tag_parts)}"


_metrics_backend: MetricsBackend = InMemoryMetricsBackend()


def get_metrics() -> MetricsBackend:
    return _metrics_backend


def set_metrics_backend(backend: MetricsBackend) -> None:
    global _metrics_backend
    _metrics_backend = backend
