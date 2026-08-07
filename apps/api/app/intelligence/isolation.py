"""Seeded Isolation Forest anomaly scoring.

The isolation forest is the one *learned* component in the layer, and it is
made deterministic by construction: a fixed ``random_state`` (from the
detector config) and a single worker thread produce identical scores for
identical features, on any machine, forever.

The returned 0-1 *anomaly strength* is a normalised rank of the raw
isolation score, so it composes with the statistical signals in evidence
scoring.
"""

from __future__ import annotations

from sklearn.ensemble import IsolationForest


def isolation_anomaly_scores(
    features: list[list[float]],
    random_state: int = 0,
    contamination: float = 0.05,
    n_estimators: int = 100,
) -> list[float]:
    """Return a 0-1 anomaly strength per feature row (deterministic)."""
    if not features or len(features) < 3:
        return [0.0] * len(features)
    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
        n_jobs=1,  # single worker keeps scheduling deterministic
    ).fit(features)
    raw = -model.score_samples(features)  # higher = more anomalous
    low, high = min(raw), max(raw)
    if high - low < 1e-12:
        return [0.0] * len(raw)
    return [round((value - low) / (high - low), 4) for value in raw]
