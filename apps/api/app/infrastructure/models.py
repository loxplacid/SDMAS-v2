"""Central import site for every SQLAlchemy ORM model.

The API process registers all models transitively (each domain router
imports its models module, so ``Base.metadata`` sees every table).  The
worker process starts from a much narrower import graph — it must never
import routers — so models whose tables are referenced by cross-domain
foreign keys (e.g. ``notifications.campus_id -> campuses``) can be missing
from the worker's metadata, and any flush that touches those tables fails
with ``NoReferencedTableError``.

Importing this module from a process entrypoint (worker, migration-init,
Alembic ``env.py``, scripts) registers every model on ``Base.metadata``
exactly once.  Import order is irrelevant: ``metadata.sorted_tables``
resolves FK references lazily at DDL/flush time, so simply having all
modules imported is enough.

Alembic ``env.py`` imports this module too, so ``alembic autogenerate`` /
``alembic check`` see the *complete* model set — without it they would
report every table whose domain is not in the hand-maintained import list
as "to be dropped".
"""

from __future__ import annotations

# One import per domain that defines mapped models, ordered alphabetically.
# Each module is imported for its side effect: registering that domain's
# tables on Base.metadata.
from app.domains.academic import models as academic_models  # noqa: F401
from app.domains.academic_ops import models as academic_ops_models  # noqa: F401
from app.domains.admission import models as admission_models  # noqa: F401
from app.domains.attendance import models as attendance_models  # noqa: F401
from app.domains.attendance_intelligence import (
    models as attendance_intelligence_models,  # noqa: F401
)
from app.domains.audit import models as audit_models  # noqa: F401
from app.domains.auth import models as auth_models  # noqa: F401
from app.domains.billing import models as billing_models  # noqa: F401
from app.domains.cases import models as cases_models  # noqa: F401
from app.domains.communications import models as communications_models  # noqa: F401
from app.domains.data_quality import models as data_quality_models  # noqa: F401
from app.domains.documents import models as documents_models  # noqa: F401

# Models defined outside their domain's models.py — import explicitly so
# alembic autogenerate/check and the worker see them on Base.metadata.
from app.domains.events.outbox import OutboxEvent  # noqa: F401
from app.domains.fees import models as fees_models  # noqa: F401
from app.domains.institution import models as institution_models  # noqa: F401
from app.domains.jobs import models as jobs_models  # noqa: F401
from app.domains.leave import models as leave_models  # noqa: F401
from app.domains.migration import models as migration_models  # noqa: F401
from app.domains.notifications import models as notifications_models  # noqa: F401
from app.domains.notifications.preferences import NotificationPreference  # noqa: F401
from app.domains.parent import models as parent_models  # noqa: F401
from app.domains.report_builder import models as report_builder_models  # noqa: F401
from app.domains.risk import models as risk_models  # noqa: F401
from app.domains.school_finance import models as school_finance_models  # noqa: F401
from app.domains.search import models as search_models  # noqa: F401
from app.domains.student import models as student_models  # noqa: F401
from app.domains.student_portal import models as student_portal_models  # noqa: F401
from app.domains.workflow import models as workflow_models  # noqa: F401
from app.temporal.models import TxnLog  # noqa: F401
