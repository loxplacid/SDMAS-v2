"""The Archive — bitemporal engine (milestone M1).

Engine-level primitives that make every SDMAS table time-travelable:

* ``TimeContext`` / ``time_context`` — request-scoped bitemporal context.
* ``ChangeEnvelope`` — structured old/new/actor/reason/txn record.
* ``TemporalTableRegistry`` — current ↔ history mirror mapping + DDL.
* ``TxnManager`` — close-open writes (current + history + txn_log atomic).
"""

from .context import TimeContext, set_time_context, time_context
from .envelope import CHANGE_KIND, ChangeEnvelope
from .registry import (
    TemporalError,
    TemporalTableRegistry,
    TemporalTableSpec,
    build_history_table,
    registry,
    tt_range_index_definition,
)
from .txn import TxnManager

__all__ = [
    "CHANGE_KIND",
    "ChangeEnvelope",
    "TimeContext",
    "TemporalError",
    "TemporalTableRegistry",
    "TemporalTableSpec",
    "TxnManager",
    "build_history_table",
    "registry",
    "set_time_context",
    "time_context",
    "tt_range_index_definition",
]
