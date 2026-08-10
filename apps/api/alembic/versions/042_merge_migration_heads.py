"""merge divergent migration heads into a single linear head

The migration graph had diverged into three heads:

* ``041_add_communication_context`` (cases/communications chain)
* ``c21889d4e562`` (legacy null-campus flag chain)
* ``create_temporal_txn_log`` (temporal ledger chain)

CI enforces exactly one head (``alembic heads | wc -l == 1``) and the D2
migration workspace tables must be appended linearly.  This merge revision
converges the branches so ``alembic upgrade head`` resolves cleanly.

Revision ID: 042_merge_migration_heads
Revises: 041_add_communication_context, c21889d4e562, create_temporal_txn_log
Create Date: 2026-08-10 00:00:00.000000

"""

from collections.abc import Sequence

revision: str = "042_merge_migration_heads"
down_revision: str | Sequence[str] | None = (
    "041_add_communication_context",
    "c21889d4e562",
    "create_temporal_txn_log",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge-only revision — no schema changes."""
    pass


def downgrade() -> None:
    """Merge-only revision — no schema changes."""
    pass
