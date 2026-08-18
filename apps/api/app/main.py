from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.error_handlers import (
    auth_error_handler,
    conflict_handler,
    file_validation_handler,
    forbidden_handler,
    not_found_handler,
    payment_required_handler,
    validation_handler,
)
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    PaymentRequiredError,
    ValidationError,
)
from app.core.observability import (
    configure_json_logging,
    instrument_fastapi,
    instrument_sqlalchemy,
    observability_router,
    register_observability_middleware,
    setup_opentelemetry,
)
from app.domains.academic.router import router as academic_router
from app.domains.attendance.router import router as attendance_router
from app.domains.attendance_intelligence.router import router as attendance_intelligence_router
from app.domains.auth.router import router as auth_router
from app.domains.auth.admin_router import router as admin_router
from app.domains.fees.router import router as fees_router
from app.domains.admission.router import router as admission_router
from app.domains.analytics.router import router as analytics_router
from app.domains.leave.router import router as leave_router
from app.domains.workflow.router import router as workflow_router
from app.domains.institution.router import router as institution_router
from app.domains.notifications import dispatcher as notification_dispatcher
from app.domains.notifications.handlers import register_all_handlers
from app.domains.events import event_bus
from app.domains.events.handlers import register_domain_event_handlers
from app.domains.notifications.router import router as notifications_router
from app.domains.notifications.push_router import router as push_router
from app.domains.reports.router import router as reports_router
from app.domains.report_cards.router import router as report_cards_router
from app.domains.student.router import router as student_router
from app.domains.student.lifecycle_router import router as student_lifecycle_router
from app.domains.student_360.router import router as student_360_router
from app.domains.class_360.router import router as class_360_router
from app.domains.teacher_360.router import router as teacher_360_router
from app.domains.academic_ops.router import router as academic_ops_router
from app.domains.school_finance.router import router as school_finance_router
from app.domains.report_builder.router import router as report_builder_router
from app.domains.documents.router import router as documents_router
from app.domains.communications.router import router as communications_router
from app.domains.parent.router import router as parent_router
from app.domains.search.router import router as search_router
from app.domains.jobs.router import router as jobs_router
from app.domains.migration.router import router as migration_router
from app.domains.student_portal.router import router as student_portal_router
from app.domains.command_center.router import router as command_center_router
from app.domains.risk.router import router as risk_router
from app.domains.data_quality.router import router as data_quality_router
from app.domains.cases.router import router as cases_router
from app.domains.timeline.router import router as timeline_router
from app.infrastructure.database import close_db
from app.domains.audit.router import router as audit_router
from app.domains.audit.export import router as audit_export_router
from app.core.security import register_security_headers_middleware
from app.core.security.auth_gate import register_auth_gate
from app.domains.jobs.worker import JobWorker
from app.multi_tenant.middleware import register_tenant_middleware
from app.domains.billing.router import router as billing_router
from app.domains.exceptions.router import router as exception_router
from app.domains.ledger.router import router as ledger_router
from app.domains.process_mining.router import router as process_mining_router
from app.domains.compliance.router import router as compliance_router
from app.domains.billing.admin_router import router as billing_admin_router
from app.domains.billing.payments import register_provider

logger = logging.getLogger(__name__)

# Start the background workers inside the API process only when explicitly
# enabled.  In production the API serves requests only and the dedicated
# worker process (Dockerfile.worker) is the sole consumer of the jobs table
# and the event outbox, so scaling API replicas never launches competing
# workers against the same queues.
_background_worker: JobWorker | None = None
_background_outbox_worker = None
_background_scheduler = None


def _start_in_process_workers() -> None:
    """Start the job + outbox workers inside the API process (dev only).

    Only meaningful when ``settings.worker_in_process`` is true.  Registers
    the outbox handlers and job implementations so the in-process loops can
    resolve them, mirroring the dedicated worker's startup.
    """
    global _background_worker, _background_outbox_worker, _background_scheduler
    if _background_worker is not None and _background_worker.is_running:
        return

    from app.domains.jobs.loader import load_all_jobs
    load_all_jobs()

    from app.domains.events.outbox import OutboxWorker, outbox_dispatcher
    from app.domains.events.outbox_handlers import register_outbox_handlers
    register_outbox_handlers(outbox_dispatcher)

    _background_worker = JobWorker(poll_interval=5.0)
    _background_outbox_worker = OutboxWorker(
        poll_interval=settings.outbox_poll_interval,
        batch_size=settings.outbox_batch_size,
        max_attempts=settings.outbox_max_attempts,
        reap_interval=settings.outbox_reap_interval,
        stale_after=settings.outbox_stale_after,
    )
    _background_worker.start()
    _background_outbox_worker.start()

    if settings.scheduler_enabled:
        from app.domains.jobs.scheduler import Scheduler
        _background_scheduler = Scheduler(
            poll_interval=settings.scheduler_poll_interval
        )
        _background_scheduler.start()

    logger.info(
        "In-process job + outbox workers started (WORKER_IN_PROCESS); "
        "scheduler=%s",
        "enabled" if _background_scheduler is not None else "disabled",
    )


async def _stop_in_process_workers() -> None:
    global _background_worker, _background_outbox_worker, _background_scheduler
    if _background_scheduler is not None:
        await _background_scheduler.stop()
        _background_scheduler = None
    if _background_outbox_worker is not None:
        await _background_outbox_worker.stop()
        _background_outbox_worker = None
    if _background_worker is not None:
        await _background_worker.stop()
        _background_worker = None

configure_json_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting SDMAS API", extra={"environment": settings.environment, "version": "0.1.0"})

    setup_opentelemetry(
        app_name=settings.app_name,
        environment=settings.environment,
    )

    instrument_sqlalchemy()
    instrument_fastapi(_app)

    # Register payment provider (Razorpay for India)
    if settings.razorpay_key_id and settings.razorpay_key_secret:
        from app.domains.billing.razorpay import RazorpayProvider
        provider = RazorpayProvider(
            key_id=settings.razorpay_key_id,
            key_secret=settings.razorpay_key_secret,
        )
        register_provider("razorpay", provider)
        logger.info("Razorpay payment provider registered")

    # Wire up notification event handlers
    register_all_handlers(notification_dispatcher)
    logger.info(
        "Notification event dispatcher initialised with %d handler(s)",
        notification_dispatcher.handler_count,
    )

    # Wire up domain event handlers (audit, risk, notification, lifecycle)
    register_domain_event_handlers(event_bus)
    logger.info(
        "Domain event dispatcher initialised with %d handler(s)",
        event_bus.handler_count,
    )

    # Seed report definitions into database
    from app.infrastructure.database import get_session
    from app.domains.report_builder.registry import ReportRegistry
    import app.domains.report_builder.builders  # noqa: F401
    try:
        async for session in get_session():
            await ReportRegistry.ensure_definitions(session)
            logger.info("Report definitions seeded (%d registered)", len(ReportRegistry.get_all()))
    except Exception as exc:
        logger.warning("Could not seed report definitions: %s", exc)

    # Seed document categories
    from app.domains.documents.service import DocumentCategoryService
    try:
        async for session in get_session():
            await DocumentCategoryService(session).seed_categories()
            logger.info("Document categories seeded")
    except Exception as exc:
        logger.warning("Could not seed document categories: %s", exc)

    # Start the background workers inside the API process only when the
    # dedicated worker is absent (single-process dev / tests).
    if settings.worker_in_process:
        _start_in_process_workers()

    yield

    logger.info("Shutting down SDMAS API — stopping background workers")
    await _stop_in_process_workers()
    logger.info("Shutting down SDMAS API — closing database connections")
    await close_db()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    # Interactive docs (Swagger/ReDoc) and the raw OpenAPI schema expose
    # internal route structure — disable them in production.
    docs_url=None if settings.is_production() else "/docs",
    redoc_url=None if settings.is_production() else "/redoc",
    openapi_url=None if settings.is_production() else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register security headers middleware (outermost — runs last on response)
register_security_headers_middleware(app)

# Register observability middleware (request IDs, correlation IDs, latency metrics)
register_observability_middleware(app)

# Register tenant context middleware
register_tenant_middleware(app)

# Register audit middleware (must be after tenant middleware)
from app.domains.audit.middleware import register_audit_middleware
register_audit_middleware(app)

# Register the default-deny authentication gate LAST so it runs outermost
# (first on every request).  Only the explicit public allowlist bypasses
# authentication; everything else fails closed with 401.
register_auth_gate(app)

app.add_exception_handler(NotFoundError, not_found_handler)
app.add_exception_handler(ConflictError, conflict_handler)
app.add_exception_handler(ValidationError, validation_handler)
app.add_exception_handler(AuthenticationError, auth_error_handler)
app.add_exception_handler(AuthorizationError, forbidden_handler)
app.add_exception_handler(PaymentRequiredError, payment_required_handler)
# Rejected uploads (oversized / disallowed extension / disallowed MIME
# content) return a clean 400 instead of an unhandled 500.
from app.domains.documents.validation import FileValidationError
app.add_exception_handler(FileValidationError, file_validation_handler)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(student_router)
app.include_router(student_lifecycle_router)
app.include_router(academic_router)
app.include_router(attendance_router)
app.include_router(attendance_intelligence_router)
app.include_router(fees_router)
app.include_router(notifications_router)
app.include_router(push_router)
app.include_router(analytics_router)
app.include_router(reports_router)
app.include_router(report_cards_router)
app.include_router(institution_router)
app.include_router(admission_router)
app.include_router(workflow_router)
app.include_router(leave_router)
# Export router first: it declares the literal ``/export`` path, which
# must win over the ``/{entry_id}`` catch-all in ``audit_router``.
app.include_router(audit_export_router)
app.include_router(audit_router)
app.include_router(student_360_router)
app.include_router(class_360_router)
app.include_router(teacher_360_router)
app.include_router(academic_ops_router)
app.include_router(school_finance_router)
app.include_router(report_builder_router)
app.include_router(documents_router)
app.include_router(communications_router)
app.include_router(parent_router)
app.include_router(search_router)
app.include_router(student_portal_router)
app.include_router(command_center_router)
app.include_router(risk_router)
app.include_router(data_quality_router)
app.include_router(cases_router)
app.include_router(timeline_router)
app.include_router(jobs_router)
app.include_router(migration_router)
app.include_router(billing_router)
app.include_router(billing_admin_router)
app.include_router(exception_router)
app.include_router(ledger_router)
app.include_router(process_mining_router)
app.include_router(compliance_router)

# Observability routes: /health, /ready, /metrics
app.include_router(observability_router)