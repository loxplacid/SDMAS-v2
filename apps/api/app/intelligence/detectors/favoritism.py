"""Teacher-favoritism detection — the rule-engine showcase.

A pure, thresholded rule over persisted grade records:

1. per exam: class average % (the reference distribution);
2. per (teacher, student): average % gap vs that reference across exams;
3. per student: ability proxy = average % in subjects *not* taught by the
   teacher under review.

A finding fires only when the gap is **persistent** (≥ ``min_exams``),
**large** (≥ ``gap_threshold`` points) and the student is **not** top of the
cohort elsewhere (ability < ``ability_floor``) — the ability control is the
false-positive guard that separates genuine high performers from inflated
marks.

Rules are pure functions of persisted data, evaluated at a point in time —
the same contract as ``domains/risk``.
"""

from __future__ import annotations

from app.intelligence.config import IntelligenceConfig
from app.intelligence.detectors.base import Detector
from app.intelligence.graph import EntityGraph
from app.intelligence.scoring import Evidence, EvidenceScorer, Finding


class TeacherFavoritismDetector(Detector):
    detector_id = "teacher_favoritism"
    name = "Teacher favoritism"
    category = "integrity"

    def run(self, graph: EntityGraph, config: IntelligenceConfig) -> list[Finding]:
        cfg = config.for_detector(self.detector_id)
        t = cfg.thresholds
        gap_threshold = float(t.get("gap_threshold", 15.0))
        min_exams = int(t.get("min_exams", 3))
        ability_floor = float(t.get("ability_floor", 60.0))

        records = graph.records_with_label("grade")

        def pct(props: dict) -> float:
            max_marks = float(props.get("max_marks", 0) or 0)
            if max_marks <= 0:
                return 0.0
            return float(props.get("marks", 0)) / max_marks * 100.0

        # Per-(exam, subject) reference distributions: the class average a
        # student's mark is compared against must come from the *same* exam
        # *and* subject, or cross-subject noise inflates/dilutes the gap.
        exam_subject_averages: dict[tuple[int, str], float] = {}
        by_exam_subject: dict[tuple[int, str], list] = {}
        for record in records:
            key = (int(record.props["exam_id"]), str(record.props["subject"]))
            by_exam_subject.setdefault(key, []).append(record)
        for key, group in by_exam_subject.items():
            exam_subject_averages[key] = sum(pct(r.props) for r in group) / len(group)

        # Per-(teacher, student) gaps and per-(student, subject) averages.
        gaps: dict[tuple[int, int], list[float]] = {}
        subject_student_avg: dict[tuple[str, int], list[float]] = {}
        teacher_subjects: dict[int, set[str]] = {}
        for record in records:
            props = record.props
            teacher_id = int(props["teacher_id"])
            student_id = int(props["student_id"])
            subject = str(props["subject"])
            exam_id = int(props["exam_id"])
            marks_pct = pct(props)
            gaps.setdefault((teacher_id, student_id), []).append(
                marks_pct - exam_subject_averages[(exam_id, subject)]
            )
            subject_student_avg.setdefault((subject, student_id), []).append(marks_pct)
            teacher_subjects.setdefault(teacher_id, set()).add(subject)

        scorer = EvidenceScorer(cfg.min_score)
        findings: list[Finding] = []
        for (teacher_id, student_id), gap_list in sorted(gaps.items()):
            if len(gap_list) < min_exams:
                continue
            avg_gap = sum(gap_list) / len(gap_list)
            if avg_gap < gap_threshold:
                continue
            reviewed_subjects = teacher_subjects.get(teacher_id, set())
            other_averages = [
                sum(values) / len(values)
                for (subject, sid), values in subject_student_avg.items()
                if sid == student_id and subject not in reviewed_subjects
            ]
            ability = sum(other_averages) / len(other_averages) if other_averages else None
            if ability is not None and ability >= ability_floor:
                continue  # genuine high performer — not favoritism
            gap_normalised = min(avg_gap / 30.0, 1.0)
            # Ability strength is *inverted*: a low ability elsewhere is the
            # suspicious case (the student is not a genuine high performer),
            # so evidence must peak when ability is at/under zero.
            ability_strength = 1.0 - min(ability or 0.0, ability_floor) / ability_floor
            evidence = [
                Evidence(
                    "persistent_gap",
                    round(gap_normalised, 4),
                    0.5,
                    f"avg gap +{avg_gap:.1f} pts",
                ),
                Evidence(
                    "exam_count",
                    min(len(gap_list) / min_exams, 1.0),
                    0.2,
                    f"{len(gap_list)} exams",
                ),
                Evidence(
                    "ability_control",
                    round(max(ability_strength, 0.0), 4),
                    0.3,
                    f"ability proxy {ability:.1f}% in other subjects",
                ),
            ]
            finding = scorer.finding(
                rule_code=self.detector_id,
                category=self.category,
                entity_type="student",
                entity_id=student_id,
                evidence=evidence,
                reason=(
                    f"Teacher {teacher_id} awards student {student_id} "
                    f"+{avg_gap:.1f} pts over the class average across "
                    f"{len(gap_list)} exams; ability elsewhere is only "
                    f"{ability:.1f}%"
                ),
                recommended_action=(
                    "Discuss with the academic head; sample-mark the teacher's grading."
                ),
            )
            if finding is not None:
                findings.append(finding)
        return sorted(findings, key=lambda f: (-f.score, f.entity_id))
