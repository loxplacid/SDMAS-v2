"""Central import site for every ``@register_job`` implementation.

The worker process imports this module at startup so each job module's
module-level ``@register_job`` decorator runs and ``get_job_class`` resolves
every job type.  The API process never imports it — the API must not
execute jobs (that is the worker's job), it only *enqueues* them.

Adding a new job implementation means adding its module to ``_JOB_MODULES``
(or simply importing it) — no other wiring is required.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Job implementation modules.  Importing each module runs its
#: ``@register_job`` decorators against the global registry.
_JOB_MODULES = (
    "app.domains.report_builder.jobs",
    "app.domains.jobs.periodic_jobs",
)


def load_all_jobs() -> None:
    """Import every job module so the registry is populated."""
    from importlib import import_module

    for module in _JOB_MODULES:
        try:
            import_module(module)
            logger.debug("Loaded job module %s", module)
        except ImportError:
            logger.exception("Failed to load job module %s", module)
