"""Relationship intelligence test suite.

Covers similarity scoring, statistical primitives, algorithm wrappers, each
implemented detector, and pipeline determinism + false-positive reduction.
Every test is deterministic: no RNG, no network, no persistence.
"""

from __future__ import annotations

from app.intelligence.clustering import dbscan_clusters
from app.intelligence.config import IntelligenceConfig
from app.intelligence.detectors.attendance_anomaly import AttendanceAnomalyDetector
from app.intelligence.detectors.cheating_cluster import CheatingClusterDetector
from app.intelligence.detectors.duplicates import DuplicateStudentsDetector
from app.intelligence.detectors.favoritism import TeacherFavoritismDetector
from app.intelligence.detectors.social_cluster import SocialClusterDetector
from app.intelligence.graph import EdgeRecord, EntityGraph, EntityRecord
from app.intelligence.isolation import isolation_anomaly_scores
from app.intelligence.pipeline import DetectionPipeline
from app.intelligence.similarity import (
    jaro,
    jaro_winkler,
    normalize_email,
    normalize_phone,
    normalize_text,
    record_similarity,
    token_jaccard,
)
from app.intelligence.stats import mad, modified_z_score, z_score

# ---------------------------------------------------------------------------
# Similarity scoring
# ---------------------------------------------------------------------------


def test_normalization_is_deterministic_and_aggressive():
    assert normalize_text("  John   O'CONNOR, Jr.  ") == "john o connor jr"
    assert normalize_phone("+91 (982) 013-4567") == "919820134567"
    assert normalize_email("  JOHN.DOE@Example.COM ") == "john.doe@example.com"


def test_jaro_and_winkler_basics():
    assert jaro("MARTHA", "MARHTA") > 0.9
    assert jaro("abc", "xyz") < 0.2
    assert jaro("", "abc") == 0.0
    assert jaro_winkler("abc", "abc") == 1.0
    # Common-prefix boost lifts near-misses.
    assert jaro_winkler("smith", "smyth") > jaro("smith", "smyth")


def test_token_jaccard_handles_word_order():
    assert token_jaccard("Priya Sharma", "Sharma Priya") == 1.0
    assert abs(token_jaccard("Priya Sharma", "Priya Kapoor") - 1.0 / 3.0) < 1e-9
    assert token_jaccard("", "x") == 0.0


def test_record_similarity_weights_identity_fields():
    a = {
        "name": "Priya Sharma",
        "guardian_name": "Rakesh Sharma",
        "dob": "2010-05-01",
        "address": "12 MG Road",
    }
    b = {
        "name": "Priya Sharma",
        "guardian_name": "Rakesh Sharma",
        "dob": "2010-05-01",
        "address": "12 MG Road",
    }
    c = {
        "name": "Anil Kumar",
        "guardian_name": "Suresh Kumar",
        "dob": "2009-11-30",
        "address": "88 Lake View",
    }
    assert record_similarity(a, b) == 1.0
    assert record_similarity(a, c) < 0.5
    # Missing fields are skipped, not zeroed.
    assert record_similarity({"name": "A B"}, {"name": "A B"}) == 1.0


# ---------------------------------------------------------------------------
# Statistical primitives
# ---------------------------------------------------------------------------


def test_mad_and_modified_z_are_robust():
    values = [0.5, 0.51, 0.49, 0.52, 0.5, 0.05]  # one clear outlier
    spread = mad(values)
    assert spread > 0.0
    assert abs(modified_z_score(0.05, 0.5, spread)) > 3.5  # flagged
    assert abs(modified_z_score(0.51, 0.5, spread)) < 1.0  # not flagged


def test_z_score_guards_zero_spread():
    assert z_score(1.0, 1.0, 0.0) == 0.0


# ---------------------------------------------------------------------------
# Algorithm wrappers
# ---------------------------------------------------------------------------


def test_dbscan_hamming_clusters_similar_vectors():
    near = [0, 1, 2, 3, 4, 5]
    features = [
        near,
        [0, 1, 2, 3, 4, 5],
        [0, 1, 2, 3, 4, 6],
        [5, 4, 3, 2, 1, 0],
        [5, 4, 3, 2, 1, 1],
        [5, 4, 3, 2, 1, 2],
        [9, 9, 9, 9, 9, 9],
    ]
    clusters = dbscan_clusters(features, eps=0.4, min_samples=3, metric="hamming")
    sizes = sorted(len(v) for v in clusters.values())
    assert sizes == [3, 3]  # two tight groups, noise point dropped


def test_isolation_scores_are_seeded_and_normalised():
    features = [[0.1, 0.2], [0.15, 0.25], [0.12, 0.22], [0.9, 0.9]]
    first = isolation_anomaly_scores(features, random_state=7)
    second = isolation_anomaly_scores(features, random_state=7)
    assert first == second  # deterministic
    assert max(first) == 1.0  # normalised 0-1, outlier is the max


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_graph(campus_id: int = 1) -> EntityGraph:
    """A small deterministic campus: 7 students, dense co-attendance group.

    Students 1, 3, 4, 5, 7 attend normally (~0.92); students 2 and 6 are the
    low-attendance outliers the anomaly detector should find. Students 1 and
    2 share name/phone/email on purpose (the duplicate pair).
    """
    students = [
        EntityRecord(
            "student",
            1,
            {
                "name": "Priya Sharma",
                "phone": "919820134567",
                "email": "priya@example.com",
                "attendance_rate": 0.92,
                "recent_rate": 0.9,
                "max_consecutive_absences": 1,
            },
        ),
        EntityRecord(
            "student",
            2,
            {
                "name": "Priya Sharma",
                "phone": "919820134567",
                "email": "priya@example.com",
                "attendance_rate": 0.5,
                "recent_rate": 0.4,
                "max_consecutive_absences": 6,
            },
        ),
        EntityRecord(
            "student",
            3,
            {
                "name": "Rahul Verma",
                "phone": "912345678901",
                "email": "rahul@example.com",
                "attendance_rate": 0.9,
                "recent_rate": 0.91,
                "max_consecutive_absences": 1,
            },
        ),
        EntityRecord(
            "student",
            4,
            {
                "name": "Sneha Iyer",
                "phone": "919876543210",
                "email": "sneha@example.com",
                "attendance_rate": 0.93,
                "recent_rate": 0.92,
                "max_consecutive_absences": 0,
            },
        ),
        EntityRecord(
            "student",
            5,
            {
                "name": "Karan Singh",
                "phone": "919123456780",
                "email": "karan@example.com",
                "attendance_rate": 0.91,
                "recent_rate": 0.9,
                "max_consecutive_absences": 1,
            },
        ),
        EntityRecord(
            "student",
            6,
            {
                "name": "Meera Nair",
                "phone": "919000111222",
                "email": "meera@example.com",
                "attendance_rate": 0.5,
                "recent_rate": 0.45,
                "max_consecutive_absences": 5,
            },
        ),
        EntityRecord(
            "student",
            7,
            {
                "name": "Arjun Das",
                "phone": "919555123456",
                "email": "arjun@example.com",
                "attendance_rate": 0.94,
                "recent_rate": 0.95,
                "max_consecutive_absences": 0,
            },
        ),
    ]
    edges = [
        # Co-attendance: students 1, 3, 4, 5, 7 form a dense 5-member group.
        EdgeRecord("co_attendance", "student", 1, "student", 3, weight=3.0),
        EdgeRecord("co_attendance", "student", 1, "student", 4, weight=2.0),
        EdgeRecord("co_attendance", "student", 1, "student", 5, weight=2.0),
        EdgeRecord("co_attendance", "student", 3, "student", 4, weight=3.0),
        EdgeRecord("co_attendance", "student", 3, "student", 5, weight=2.0),
        EdgeRecord("co_attendance", "student", 4, "student", 5, weight=3.0),
        EdgeRecord("co_attendance", "student", 1, "student", 7, weight=2.0),
        EdgeRecord("co_attendance", "student", 3, "student", 7, weight=2.0),
        EdgeRecord("co_attendance", "student", 4, "student", 7, weight=2.0),
        EdgeRecord("co_attendance", "student", 2, "student", 6, weight=1.0),
    ]
    return EntityGraph(campus_id=campus_id, nodes=tuple(students), edges=tuple(edges))


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


def test_duplicate_students_finds_same_person_and_skips_unrelated():
    graph = make_graph()
    findings = DuplicateStudentsDetector().run(graph, IntelligenceConfig())
    pairs = {f.entity_id for f in findings}
    assert pairs == {1}  # student 1 (vs 2) — same phone + email + name
    assert all(f.score >= 45.0 for f in findings)


def test_duplicate_detector_is_deterministic():
    graph = make_graph()
    a = DuplicateStudentsDetector().run(graph, IntelligenceConfig())
    b = DuplicateStudentsDetector().run(graph, IntelligenceConfig())
    assert a == b


# ---------------------------------------------------------------------------
# Attendance anomaly
# ---------------------------------------------------------------------------


def test_attendance_anomaly_flags_low_attendee_outliers_not_the_majority():
    graph = make_graph()
    findings = AttendanceAnomalyDetector().run(graph, IntelligenceConfig())
    # The cohort median is ~0.92 with tiny MAD: the two low attendees (2, 6)
    # deviate by >3.5 MAD while the high-attendance majority does not. The
    # seeded isolation forest must agree (consensus), and must never flag a
    # member of the majority cohort.
    flagged = {f.entity_id for f in findings}
    assert flagged == {2, 6}  # both low attendees, nothing else
    assert all(f.category == "anomaly" for f in findings)


def test_attendance_anomaly_deterministic_across_seed_override():
    config = IntelligenceConfig().merged({"attendance_anomaly": {"random_state": 42}})
    a = AttendanceAnomalyDetector().run(make_graph(), config)
    b = AttendanceAnomalyDetector().run(make_graph(), config)
    assert a == b  # seeded model: identical findings every run


# ---------------------------------------------------------------------------
# Cheating cluster
# ---------------------------------------------------------------------------


def _exam_graph() -> EntityGraph:
    answers = {
        1: {"q1": "b", "q2": "a", "q3": "c", "q4": "d", "q5": "b", "q6": "c"},
        2: {"q1": "b", "q2": "a", "q3": "c", "q4": "d", "q5": "b", "q6": "c"},
        3: {"q1": "b", "q2": "a", "q3": "c", "q4": "d", "q5": "b", "q6": "a"},
        4: {"q1": "a", "q2": "b", "q3": "a", "q4": "b", "q5": "a", "q6": "b"},
        5: {"q1": "a", "q2": "b", "q3": "a", "q4": "b", "q5": "a", "q6": "b"},
        6: {"q1": "a", "q2": "b", "q3": "a", "q4": "b", "q5": "a", "q6": "c"},
        7: {"q1": "c", "q2": "d", "q3": "c", "q4": "a", "q5": "d", "q6": "d"},
    }
    nodes = [
        EntityRecord(
            "exam_response",
            sid,
            {"exam_id": 101, "student_id": sid, "answers": answers[sid]},
        )
        for sid in sorted(answers)
    ]
    return EntityGraph(campus_id=1, nodes=tuple(nodes))


def test_cheating_cluster_detects_implausible_answer_agreement():
    graph = _exam_graph()
    findings = CheatingClusterDetector().run(graph, IntelligenceConfig())
    assert findings
    # Cluster of {1,2,3} and {4,5,6} — identical-answer pairs.
    for f in findings:
        assert f.score >= 55.0
        assert "101" in f.reason


def test_cheating_below_agreement_threshold_does_not_fire():
    # Same graph, stricter agreement bar (0.90 > the ~0.89 achieved): the
    # answer-sheet agreement is a review signal only — no finding.
    config = IntelligenceConfig().merged(
        {"cheating_cluster": {"thresholds": {"agreement_threshold": 0.90}}}
    )
    findings = CheatingClusterDetector().run(_exam_graph(), config)
    assert findings == []


# ---------------------------------------------------------------------------
# Teacher favoritism
# ---------------------------------------------------------------------------


def _grade_graph(english_marks: tuple[int, int, int] = (40, 42, 38)) -> EntityGraph:
    """3 exams; teacher 10 teaches math, teacher 11 english.

    Student 1 persistently scores ~+15 pts over the per-(exam, subject) math
    class average under teacher 10, yet poorly in english (teacher 11) — the
    ability control. Student 2 scores *below* the math average: no finding.
    """
    rows = []
    n = 0
    for exam_id, math_marks in ((1, (90, 60)), (2, (88, 55)), (3, (86, 58))):
        s1_math, s2_math = math_marks
        for subject, s1, s2 in (
            ("math", s1_math, s2_math),
            ("english", english_marks[exam_id - 1], 60),
        ):
            n += 1
            rows.append(
                EntityRecord(
                    "grade",
                    n,
                    {
                        "exam_id": exam_id,
                        "student_id": 1,
                        "teacher_id": 10 if subject == "math" else 11,
                        "subject": subject,
                        "marks": s1,
                        "max_marks": 100,
                    },
                )
            )
            n += 1
            rows.append(
                EntityRecord(
                    "grade",
                    n,
                    {
                        "exam_id": exam_id,
                        "student_id": 2,
                        "teacher_id": 10 if subject == "math" else 11,
                        "subject": subject,
                        "marks": s2,
                        "max_marks": 100,
                    },
                )
            )
    return EntityGraph(campus_id=1, nodes=tuple(rows))


def test_favoritism_flags_persistent_gap_below_ability_floor():
    graph = _grade_graph()
    findings = TeacherFavoritismDetector().run(graph, IntelligenceConfig())
    assert findings
    flagged = {(f.rule_code, f.entity_id) for f in findings}
    assert ("teacher_favoritism", 1) in flagged
    # Ability control: student 1 averages ~40% in english (teacher 11) —
    # well below the 60 floor, so the +15 pt math gap is suspicious.
    assert all(f.score >= 50.0 for f in findings)


def test_favoritism_suppresses_genuine_high_performer():
    # Same math pattern, but student 1 is a strong english student too —
    # the ability control must suppress the finding (no false positive).
    graph = _grade_graph(english_marks=(82, 84, 80))
    findings = TeacherFavoritismDetector().run(graph, IntelligenceConfig())
    flagged = {(f.rule_code, f.entity_id) for f in findings}
    assert ("teacher_favoritism", 1) not in flagged


# ---------------------------------------------------------------------------
# Social cluster
# ---------------------------------------------------------------------------


def test_social_cluster_finds_dense_co_attendance_community():
    graph = make_graph()
    findings = SocialClusterDetector().run(graph, IntelligenceConfig())
    assert findings
    f = findings[0]
    assert f.category == "social"
    assert "community of 5" in f.reason  # {1,3,4,5,7} are dense
    assert f.score >= 30.0


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def test_pipeline_runs_all_detectors_and_dedupes():
    graph = make_graph()
    report = DetectionPipeline().run(graph)
    assert report.campus_id == 1
    assert report.total >= 2
    assert report.enabled_detectors == tuple(
        sorted(
            [
                "duplicate_students",
                "attendance_anomaly",
                "cheating_cluster",
                "teacher_favoritism",
                "social_cluster",
            ]
        )
    )
    # One finding per (rule, entity) — no duplicates.
    keys = {(f.rule_code, f.entity_id) for f in report.findings}
    assert len(keys) == len(report.findings)
    # Findings sorted by score desc.
    scores = [f.score for f in report.findings]
    assert scores == sorted(scores, reverse=True)
    # Categories counted.
    assert sum(report.counts_by_category.values()) == report.total


def test_pipeline_is_deterministic_and_campus_scoped():
    a = DetectionPipeline().run(make_graph(1))
    b = DetectionPipeline().run(make_graph(1))
    assert a.findings == b.findings
    other = DetectionPipeline().run(make_graph(2))
    assert other.campus_id == 2


def test_pipeline_disables_detectors_via_config():
    config = IntelligenceConfig().merged(
        {"attendance_anomaly": {"enabled": False}, "social_cluster": {"enabled": False}}
    )
    report = DetectionPipeline(config=config).run(make_graph())
    assert "attendance_anomaly" not in report.enabled_detectors
    assert "social_cluster" not in report.enabled_detectors
    assert all(f.rule_code not in {"attendance_anomaly", "social_cluster"} for f in report.findings)


def test_pipeline_noise_floor_trims_weak_findings():
    graph = make_graph()
    default = DetectionPipeline().run(graph)
    strict = DetectionPipeline(noise_floor=80.0).run(graph)
    # The floor is a safety net below the per-detector min_scores: raising it
    # above the attendance scores (~65) trims those findings only.
    assert any(f.rule_code == "attendance_anomaly" for f in default.findings)
    assert all(f.score >= 80.0 for f in strict.findings)
    assert not any(f.rule_code == "attendance_anomaly" for f in strict.findings)
    assert strict.total < default.total


def test_config_rejects_unknown_detector():
    try:
        IntelligenceConfig().merged({"nope": {"enabled": True}})
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
