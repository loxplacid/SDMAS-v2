"""Deterministic process-mining service (TASK 19).

Reads from existing persisted event sources and projects process-mining
metrics.  No external platforms, no AI narratives, no randomness.

Primary data sources:
  - ``approval_history`` + ``workflow_instances`` — structured workflows
  - ``case_events`` + ``cases`` — operational case management
  - ``system_exception_events`` + ``system_exceptions`` — exception lifecycle

Each analysis method builds an **event log** from these sources, then
computes deterministic metrics on top of it.
"""

from __future__ import annotations

import datetime
import logging
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.cases.models import Case, CaseEvent
from app.domains.exceptions.models import SystemException, SystemExceptionEvent
from app.domains.process_mining.schemas import (
    Activity,
    Bottleneck,
    CaseTrace,
    ProcessAnalysisResponse,
    ProcessGraph,
    ProcessSummary,
    ProcessVariant,
    ReworkInstance,
    SLAViolation,
    Transition,
    TransitionFrequency,
)
from app.domains.process_mining.schemas import (
    CaseEvent as CaseEventSchema,
)
from app.domains.workflow.models import (
    ApprovalHistory,
    Workflow,
    WorkflowInstance,
)

logger = logging.getLogger(__name__)

# Terminal states for each source
_WORKFLOW_TERMINAL = {"completed", "rejected", "cancelled"}
_CASE_TERMINAL = {"resolved", "closed"}
_EXCEPTION_TERMINAL = {"resolved", "closed"}

# Default SLA limits by priority (seconds)
_DEFAULT_SLA: dict[str, float] = {
    "critical": 4 * 3600,  # 4 hours
    "high": 24 * 3600,  # 24 hours
    "medium": 72 * 3600,  # 3 days
    "low": 168 * 3600,  # 7 days
}


@dataclass
class _EventLogEntry:
    """A single event in the normalized event log."""

    case_id: str
    activity: str
    timestamp: datetime.datetime
    entity_type: str
    entity_id: int
    actor: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class _CaseInfo:
    """Aggregated info for one case."""

    case_id: str
    entity_type: str
    entity_id: int
    events: list[_EventLogEntry] = field(default_factory=list)
    started_at: datetime.datetime | None = None
    ended_at: datetime.datetime | None = None
    status: str = "active"


class ProcessMiningService:
    """Deterministic process-mining projections.

    All methods are read-only and tenant-scoped.  A failing source
    degrades gracefully — the remaining sources still render.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ====================================================================
    # Main entry point
    # ====================================================================

    async def analyze(
        self,
        campus_id: int | None,
        *,
        source: str | None = None,
        limit: int = 1000,
    ) -> ProcessAnalysisResponse:
        """Run full process analysis from all available sources."""
        event_log = await self._build_event_log(campus_id, source, limit)
        cases = self._group_into_cases(event_log)

        graph = self._discover_process(cases)
        variants = self._find_variants(cases)
        bottlenecks = self._find_bottlenecks(cases)
        transitions = self._transition_frequency(cases)
        rework = self._detect_rework(cases)
        sla_violations = self._check_sla(cases)
        summary = self._build_summary(
            cases, graph, variants, bottlenecks, rework, sla_violations
        )

        case_traces = [
            self._case_to_trace(c) for c in cases.values()
        ]

        return ProcessAnalysisResponse(
            summary=summary,
            graph=graph,
            variants=variants,
            bottlenecks=bottlenecks,
            transitions=transitions,
            rework=rework,
            sla_violations=sla_violations,
            cases=case_traces,
        )

    # ====================================================================
    # 1. Event log construction
    # ====================================================================

    async def _build_event_log(
        self,
        campus_id: int | None,
        source: str | None,
        limit: int,
    ) -> list[_EventLogEntry]:
        """Build a normalized event log from all persisted sources."""
        log: list[_EventLogEntry] = []
        sources = [source] if source else [
            "workflow", "case", "exception",
        ]

        for src in sources:
            try:
                if src == "workflow":
                    log.extend(
                        await self._workflow_events(campus_id, limit)
                    )
                elif src == "case":
                    log.extend(
                        await self._case_events(campus_id, limit)
                    )
                elif src == "exception":
                    log.extend(
                        await self._exception_events(campus_id, limit)
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Process mining source %s failed: %s", src, exc
                )

        log.sort(key=lambda e: e.timestamp)
        return log

    async def _workflow_events(
        self, campus_id: int | None, limit: int
    ) -> list[_EventLogEntry]:
        """Fetch workflow events from approval_history."""
        q = (
            select(ApprovalHistory, WorkflowInstance, Workflow.name)
            .join(
                WorkflowInstance,
                ApprovalHistory.instance_id == WorkflowInstance.id,
            )
            .join(Workflow, WorkflowInstance.workflow_id == Workflow.id)
        )
        conditions: list = []
        if campus_id is not None:
            conditions.append(WorkflowInstance.campus_id == campus_id)
        if conditions:
            q = q.where(*conditions)
        q = (
            q.order_by(ApprovalHistory.created_at.desc())
            .limit(limit)
        )
        rows = (await self.session.execute(q)).all()

        events: list[_EventLogEntry] = []
        for ah, wi, wf_name in rows:
            actor = f"user #{ah.actor_id}" if ah.actor_id else "system"
            events.append(
                _EventLogEntry(
                    case_id=f"wf:{wi.id}",
                    activity=ah.action or "unknown",
                    timestamp=ah.created_at,
                    entity_type=wi.entity_type,
                    entity_id=wi.entity_id,
                    actor=actor,
                    metadata={
                        "instance_id": wi.id,
                        "workflow_name": wf_name,
                        "workflow_status": wi.status,
                    },
                )
            )
        return events

    async def _case_events(
        self, campus_id: int | None, limit: int
    ) -> list[_EventLogEntry]:
        """Fetch events from case_events."""
        q = (
            select(CaseEvent, Case)
            .join(Case, CaseEvent.case_id == Case.id)
        )
        conditions: list = []
        if campus_id is not None:
            conditions.append(Case.campus_id == campus_id)
        if conditions:
            q = q.where(*conditions)
        q = q.order_by(CaseEvent.created_at.desc()).limit(limit)
        rows = (await self.session.execute(q)).all()

        events: list[_EventLogEntry] = []
        for ce, case in rows:
            actor = ce.actor_name or (
                f"user #{ce.actor_id}" if ce.actor_id else "system"
            )
            events.append(
                _EventLogEntry(
                    case_id=f"case:{case.id}",
                    activity=ce.event_type.lower(),
                    timestamp=ce.created_at,
                    entity_type="case",
                    entity_id=case.id,
                    actor=actor,
                    metadata={
                        "case_number": case.case_number,
                        "case_type": case.case_type,
                        "case_status": case.status,
                    },
                )
            )
        return events

    async def _exception_events(
        self, campus_id: int | None, limit: int
    ) -> list[_EventLogEntry]:
        """Fetch events from system_exception_events."""
        q = (
            select(SystemExceptionEvent, SystemException)
            .join(
                SystemException,
                SystemExceptionEvent.exception_id == SystemException.id,
            )
        )
        conditions: list = []
        if campus_id is not None:
            conditions.append(SystemException.campus_id == campus_id)
        if conditions:
            q = q.where(*conditions)
        q = (
            q.order_by(SystemExceptionEvent.created_at.desc())
            .limit(limit)
        )
        rows = (await self.session.execute(q)).all()

        events: list[_EventLogEntry] = []
        for see, exc in rows:
            actor = see.actor_name or (
                f"user #{see.actor_id}" if see.actor_id else "system"
            )
            events.append(
                _EventLogEntry(
                    case_id=f"exc:{exc.id}",
                    activity=see.event_type.lower(),
                    timestamp=see.created_at,
                    entity_type="exception",
                    entity_id=exc.id,
                    actor=actor,
                    metadata={
                        "exception_type": exc.exception_type,
                        "severity": exc.severity,
                        "exception_status": exc.status,
                    },
                )
            )
        return events

    # ====================================================================
    # 2. Case identification
    # ====================================================================

    @staticmethod
    def _group_into_cases(
        event_log: list[_EventLogEntry],
    ) -> dict[str, _CaseInfo]:
        """Group events into cases by case_id."""
        cases: dict[str, _CaseInfo] = {}
        for entry in event_log:
            if entry.case_id not in cases:
                cases[entry.case_id] = _CaseInfo(
                    case_id=entry.case_id,
                    entity_type=entry.entity_type,
                    entity_id=entry.entity_id,
                )
            case = cases[entry.case_id]
            case.events.append(entry)
            if case.started_at is None or entry.timestamp < case.started_at:
                case.started_at = entry.timestamp
            if case.ended_at is None or entry.timestamp > case.ended_at:
                case.ended_at = entry.timestamp
        return cases

    # ====================================================================
    # 3. Process discovery
    # ====================================================================

    @staticmethod
    def _discover_process(
        cases: dict[str, _CaseInfo],
    ) -> ProcessGraph:
        """Discover the process model from case event logs."""
        activity_counts: Counter[str] = Counter()
        transition_counts: Counter[tuple[str, str]] = Counter()
        activity_first: dict[str, datetime.datetime] = {}
        activity_last: dict[str, datetime.datetime] = {}
        transition_durations: dict[tuple[str, str], list[float]] = defaultdict(list)

        for case in cases.values():
            sorted_events = sorted(case.events, key=lambda e: e.timestamp)
            for i, event in enumerate(sorted_events):
                activity_counts[event.activity] += 1

                if event.activity not in activity_first:
                    activity_first[event.activity] = event.timestamp
                activity_last[event.activity] = event.timestamp

                if i > 0:
                    prev = sorted_events[i - 1]
                    edge = (prev.activity, event.activity)
                    transition_counts[edge] += 1
                    duration = (
                        event.timestamp - prev.timestamp
                    ).total_seconds()
                    transition_durations[edge].append(duration)

        total_events = sum(activity_counts.values())

        nodes = [
            Activity(
                name=name,
                count=count,
                first_seen=activity_first.get(name),
                last_seen=activity_last.get(name),
            )
            for name, count in activity_counts.most_common()
        ]

        edges = [
            Transition(
                from_activity=fr,
                to_activity=to,
                count=count,
                percentage=(count / total_events * 100)
                if total_events > 0
                else 0,
                avg_duration_seconds=(
                    statistics.mean(transition_durations[(fr, to)])
                    if transition_durations[(fr, to)]
                    else None
                ),
            )
            for (fr, to), count in transition_counts.most_common()
        ]

        return ProcessGraph(
            nodes=nodes,
            edges=edges,
            total_cases=len(cases),
            total_events=total_events,
        )

    # ====================================================================
    # 4. Process variants
    # ====================================================================

    @staticmethod
    def _find_variants(
        cases: dict[str, _CaseInfo],
    ) -> list[ProcessVariant]:
        """Find distinct execution paths through the process."""
        variant_map: dict[str, list[_CaseInfo]] = defaultdict(list)

        for case in cases.values():
            sorted_events = sorted(case.events, key=lambda e: e.timestamp)
            path_list = [e.activity for e in sorted_events]
            variant_key = " -> ".join(path_list)
            variant_map[variant_key].append(case)

        total = len(cases)
        variants: list[ProcessVariant] = []
        for idx, (path, case_list) in enumerate(
            sorted(variant_map.items(), key=lambda x: -len(x[1]))
        ):
            durations = []
            for c in case_list:
                if c.started_at and c.ended_at:
                    dur = (c.ended_at - c.started_at).total_seconds()
                    durations.append(dur)

            variants.append(
                ProcessVariant(
                    variant_id=idx + 1,
                    path=path,
                    path_list=path.split(" -> "),
                    count=len(case_list),
                    percentage=(
                        len(case_list) / total * 100 if total > 0 else 0
                    ),
                    avg_duration_seconds=(
                        statistics.mean(durations) if durations else None
                    ),
                    min_duration_seconds=(
                        min(durations) if durations else None
                    ),
                    max_duration_seconds=(
                        max(durations) if durations else None
                    ),
                )
            )

        return variants

    # ====================================================================
    # 5. Cycle time
    # ====================================================================
    # (Computed per-case in _case_to_trace; aggregated in _build_summary)

    # ====================================================================
    # 6. Bottlenecks
    # ====================================================================

    @staticmethod
    def _find_bottlenecks(
        cases: dict[str, _CaseInfo],
    ) -> list[Bottleneck]:
        """Identify steps with longest waiting times."""
        wait_times: dict[str, list[float]] = defaultdict(list)

        for case in cases.values():
            sorted_events = sorted(case.events, key=lambda e: e.timestamp)
            for i in range(1, len(sorted_events)):
                duration = (
                    sorted_events[i].timestamp
                    - sorted_events[i - 1].timestamp
                ).total_seconds()
                # The wait is attributed to the activity we're arriving at
                wait_times[sorted_events[i].activity].append(duration)

        bottlenecks: list[Bottleneck] = []
        for activity, waits in wait_times.items():
            if len(waits) < 2:
                continue
            avg = statistics.mean(waits)
            med = statistics.median(waits)
            sorted_waits = sorted(waits)
            p90_idx = int(len(sorted_waits) * 0.9)
            p90 = sorted_waits[min(p90_idx, len(sorted_waits) - 1)]
            max_w = max(waits)

            severity = "info"
            if p90 > 86400:  # > 24h
                severity = "critical"
            elif p90 > 14400:  # > 4h
                severity = "warning"

            bottlenecks.append(
                Bottleneck(
                    activity=activity,
                    avg_wait_seconds=avg,
                    median_wait_seconds=med,
                    p90_wait_seconds=p90,
                    max_wait_seconds=max_w,
                    case_count=len(waits),
                    severity=severity,
                )
            )

        bottlenecks.sort(key=lambda b: -b.p90_wait_seconds)
        return bottlenecks

    # ====================================================================
    # 7. Rework detection
    # ====================================================================

    @staticmethod
    def _detect_rework(
        cases: dict[str, _CaseInfo],
    ) -> list[ReworkInstance]:
        """Detect repeated steps within a case."""
        rework: list[ReworkInstance] = []

        for case in cases.values():
            activity_timestamps: dict[str, list[datetime.datetime]] = (
                defaultdict(list)
            )
            for event in case.events:
                activity_timestamps[event.activity].append(event.timestamp)

            for activity, timestamps in activity_timestamps.items():
                if len(timestamps) >= 2:
                    rework.append(
                        ReworkInstance(
                            case_id=case.case_id,
                            entity_type=case.entity_type,
                            entity_id=case.entity_id,
                            rework_activity=activity,
                            occurrences=len(timestamps),
                            first_occurrence=min(timestamps),
                            last_occurrence=max(timestamps),
                        )
                    )

        rework.sort(key=lambda r: -r.occurrences)
        return rework

    # ====================================================================
    # 8. SLA violation detection
    # ====================================================================

    def _check_sla(
        self,
        cases: dict[str, _CaseInfo],
        sla_limits: dict[str, float] | None = None,
    ) -> list[SLAViolation]:
        """Detect cases that exceeded their time limits."""
        limits = sla_limits or _DEFAULT_SLA
        violations: list[SLAViolation] = []
        now = datetime.datetime.now(datetime.timezone.utc).replace(
            tzinfo=None
        )

        for case in cases.values():
            if case.started_at is None:
                continue

            duration = (
                (case.ended_at or now) - case.started_at
            ).total_seconds()

            # Determine SLA limit from metadata
            priority = "medium"
            for evt in case.events:
                if "severity" in evt.metadata:
                    sev = evt.metadata["severity"]
                    if sev in ("critical", "high"):
                        priority = sev
                        break

            limit = limits.get(priority, limits["medium"])
            if duration > limit:
                sorted_events = sorted(
                    case.events, key=lambda e: e.timestamp
                )
                current = (
                    sorted_events[-1].activity if sorted_events else "unknown"
                )
                violations.append(
                    SLAViolation(
                        case_id=case.case_id,
                        entity_type=case.entity_type,
                        entity_id=case.entity_id,
                        started_at=case.started_at,
                        duration_seconds=duration,
                        sla_limit_seconds=limit,
                        overshoot_seconds=duration - limit,
                        status=case.status,
                        current_activity=current,
                    )
                )

        violations.sort(key=lambda v: -v.overshoot_seconds)
        return violations

    # ====================================================================
    # 9. Transition frequency
    # ====================================================================

    @staticmethod
    def _transition_frequency(
        cases: dict[str, _CaseInfo],
    ) -> list[TransitionFrequency]:
        """Compute frequency of each state-to-state transition."""
        counts: Counter[str] = Counter()
        durations: dict[str, list[float]] = defaultdict(list)
        total_transitions = 0

        for case in cases.values():
            sorted_events = sorted(case.events, key=lambda e: e.timestamp)
            for i in range(1, len(sorted_events)):
                prev = sorted_events[i - 1]
                curr = sorted_events[i]
                key = f"{prev.activity} -> {curr.activity}"
                counts[key] += 1
                total_transitions += 1
                dur = (
                    curr.timestamp - prev.timestamp
                ).total_seconds()
                durations[key].append(dur)

        result: list[TransitionFrequency] = []
        for transition, count in counts.most_common():
            durs = durations[transition]
            result.append(
                TransitionFrequency(
                    transition=transition,
                    count=count,
                    percentage=(
                        count / total_transitions * 100
                        if total_transitions > 0
                        else 0
                    ),
                    avg_duration_seconds=(
                        statistics.mean(durs) if durs else None
                    ),
                )
            )
        return result

    # ====================================================================
    # Helpers
    # ====================================================================

    @staticmethod
    def _case_to_trace(case: _CaseInfo) -> CaseTrace:
        """Convert internal case info to API trace model."""
        sorted_events = sorted(case.events, key=lambda e: e.timestamp)
        duration = None
        if case.started_at and case.ended_at:
            duration = (
                case.ended_at - case.started_at
            ).total_seconds()

        path = " -> ".join(e.activity for e in sorted_events)

        trace_events: list[CaseEventSchema] = []
        for i, evt in enumerate(sorted_events):
            delta = None
            if i > 0:
                delta = (
                    evt.timestamp - sorted_events[i - 1].timestamp
                ).total_seconds()
            trace_events.append(
                CaseEventSchema(
                    activity=evt.activity,
                    timestamp=evt.timestamp,
                    actor=evt.actor,
                    duration_from_previous_seconds=delta,
                )
            )

        # Determine status
        status = "active"
        if case.events:
            # Check terminal states from metadata
            for evt in case.events:
                cs = evt.metadata.get("case_status", "")
                ws = evt.metadata.get("workflow_status", "")
                es = evt.metadata.get("exception_status", "")
                if cs in _CASE_TERMINAL:
                    status = "completed"
                    break
                if ws in _WORKFLOW_TERMINAL:
                    status = "completed"
                    break
                if es in _EXCEPTION_TERMINAL:
                    status = "completed"
                    break

        return CaseTrace(
            case_id=case.case_id,
            entity_type=case.entity_type,
            entity_id=case.entity_id,
            started_at=case.started_at or datetime.datetime.min,
            ended_at=case.ended_at,
            duration_seconds=duration,
            events=trace_events,
            variant=path,
            status=status,
        )

    @staticmethod
    def _build_summary(
        cases: dict[str, _CaseInfo],
        graph: ProcessGraph,
        variants: list[ProcessVariant],
        bottlenecks: list[Bottleneck],
        rework: list[ReworkInstance],
        sla_violations: list[SLAViolation],
    ) -> ProcessSummary:
        """Build high-level summary statistics."""
        durations = []
        completed = 0
        rework_case_ids: set[str] = set()
        violation_case_ids: set[str] = set()

        for case in cases.values():
            if case.started_at and case.ended_at:
                dur = (
                    case.ended_at - case.started_at
                ).total_seconds()
                durations.append(dur)

            # Check completion
            for evt in case.events:
                cs = evt.metadata.get("case_status", "")
                ws = evt.metadata.get("workflow_status", "")
                es = evt.metadata.get("exception_status", "")
                if cs in _CASE_TERMINAL or ws in _WORKFLOW_TERMINAL or es in _EXCEPTION_TERMINAL:
                    completed += 1
                    break

        for r in rework:
            rework_case_ids.add(r.case_id)
        for v in sla_violations:
            violation_case_ids.add(v.case_id)

        total = len(cases)
        most_common = variants[0].path if variants else None

        return ProcessSummary(
            total_cases=total,
            total_events=graph.total_events,
            unique_activities=len(graph.nodes),
            unique_variants=len(variants),
            avg_cycle_time_seconds=(
                statistics.mean(durations) if durations else None
            ),
            median_cycle_time_seconds=(
                statistics.median(durations) if durations else None
            ),
            p90_cycle_time_seconds=(
                sorted(durations)[int(len(durations) * 0.9)]
                if durations
                else None
            ),
            completion_rate=completed / total if total > 0 else 0,
            rework_rate=(
                len(rework_case_ids) / total if total > 0 else 0
            ),
            sla_violation_rate=(
                len(violation_case_ids) / total if total > 0 else 0
            ),
            bottleneck_count=len(bottlenecks),
            most_common_variant=most_common,
        )
