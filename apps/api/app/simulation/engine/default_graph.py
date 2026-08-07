"""Default dependency graph wiring the shipped forecast models.

Kept as a tiny factory so the engine stays generic and callers can still
register additional plugins/metrics without editing the runner.

Dependency structure:

                 revenue    workload    attendance    dropout    rooms    transport    performance
                     │          │            │           │          │         │             │
                     │          ├────rooms───┤           │          │         │             │
                     │          │            │           │          │         │             │
                     ├──────────┼────────────┼───────────┼──────────┼─────────┼─────────────┤
                     │          ▼            ▼           ▼          ▼         ▼             ▼
                     └────► budget (revenue, workload, transport, rooms)
                             resource (workload, rooms, transport)
"""

from __future__ import annotations

from app.simulation.engine.dag import DependencyEngine, MetricSpec
from app.simulation.forecasts.attendance import attendance_spec
from app.simulation.forecasts.budget import budget_spec
from app.simulation.forecasts.dropout import dropout_spec
from app.simulation.forecasts.performance import performance_spec
from app.simulation.forecasts.resource import resource_spec
from app.simulation.forecasts.revenue import revenue_spec
from app.simulation.forecasts.rooms import rooms_spec
from app.simulation.forecasts.transport import transport_spec
from app.simulation.forecasts.workload import workload_spec


def default_specs() -> list[MetricSpec]:
    return [
        revenue_spec(),
        workload_spec(),
        attendance_spec(),
        dropout_spec(),
        rooms_spec(),
        transport_spec(),
        performance_spec(),
        budget_spec(),
        resource_spec(),
    ]


def build_default_engine() -> DependencyEngine:
    return DependencyEngine(default_specs())
