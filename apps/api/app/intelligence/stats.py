"""Deterministic statistical primitives for anomaly detection.

Pure functions over numeric sequences — no randomness, no state. The
modified z-score (median + MAD) is the robust outlier test used by the
attendance anomaly detector; unlike mean/std it is not skewed by the
outliers it is trying to find.
"""

from __future__ import annotations

from statistics import median


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return (sum((v - m) ** 2 for v in values) / (len(values) - 1)) ** 0.5


def mad(values: list[float]) -> float:
    """Median absolute deviation — the robust spread estimator."""
    if not values:
        return 0.0
    med = median(values)
    return median([abs(v - med) for v in values])


def modified_z_score(value: float, median_value: float, mad_value: float) -> float:
    """Robust z-score: 0.6745 × (value − median) / MAD.

    ``|z| > 3.5`` is the conventional outlier threshold (the 0.6745 constant
    calibrates MAD to the normal standard deviation).
    """
    if mad_value <= 1e-12:
        return 0.0
    return 0.6745 * (value - median_value) / mad_value


def z_score(value: float, mean_value: float, std_value: float) -> float:
    if std_value <= 1e-12:
        return 0.0
    return (value - mean_value) / std_value
