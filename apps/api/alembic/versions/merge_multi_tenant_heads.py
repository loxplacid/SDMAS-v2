"""merge divergent migration heads into a single linear head

The migration graph previously had three heads:

* ``028_create_migration`` (jobs/billing/migration chain)
* ``e7f3a2b1c0d9`` (search tables)
* ``021_create_guardian_links`` (parent-child links)

This merge revision converges them so that new migrations can be
appended linearly with ``alembic upgrade head``.

Revision ID: merge_multi_tenant_heads
Revises: 028_create_migration, e7f3a2b1c0d9, 021_create_guardian_links
Create Date: 2026-08-01 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "merge_multi_tenant_heads"
down_revision: Union[str, Sequence[str], None] = (
    "028_create_migration",
    "e7f3a2b1c0d9",
    "021_create_guardian_links",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge-only revision — no schema changes."""
    pass


def downgrade() -> None:
    """Merge-only revision — no schema changes."""
    pass
