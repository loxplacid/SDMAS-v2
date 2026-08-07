"""Detector registry for the detection pipeline.

The pipeline instantiates detectors by id so config toggles (``enabled``)
and the roadmap catalog stay the single source of truth.
"""

from __future__ import annotations

from app.intelligence.detectors.attendance_anomaly import AttendanceAnomalyDetector
from app.intelligence.detectors.base import Detector
from app.intelligence.detectors.cheating_cluster import CheatingClusterDetector
from app.intelligence.detectors.duplicates import DuplicateStudentsDetector
from app.intelligence.detectors.favoritism import TeacherFavoritismDetector
from app.intelligence.detectors.social_cluster import SocialClusterDetector

DETECTORS: dict[str, type[Detector]] = {
    detector.detector_id: detector
    for detector in (
        DuplicateStudentsDetector,
        AttendanceAnomalyDetector,
        CheatingClusterDetector,
        TeacherFavoritismDetector,
        SocialClusterDetector,
    )
}


def get_detector_class(detector_id: str) -> type[Detector]:
    if detector_id not in DETECTORS:
        raise KeyError(f"No detector implemented for: {detector_id}")
    return DETECTORS[detector_id]


__all__ = ["DETECTORS", "Detector", "get_detector_class"]
