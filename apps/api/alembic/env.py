import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.domains.academic.models import AcademicYear, Class, Section, Enrollment, Teacher, Subject, Term, TeacherAssignment  # noqa: F401
from app.domains.admission.models import (  # noqa: F401
    AdmissionApplication, AdmissionDocument, AdmissionInterview,
    AdmissionMeritEntry, AdmissionSeatAllocation,
)
from app.domains.attendance.models import AttendanceRecord  # noqa: F401
from app.domains.attendance_intelligence.models import (  # noqa: F401
    AbsenceReason, AttendanceCorrection, AttendanceThreshold,
    PeriodAttendance, PeriodAttendanceRecord,
)
from app.domains.leave.models import LeaveRequest  # noqa: F401
from app.domains.workflow.models import (  # noqa: F401
    Workflow, WorkflowStep, WorkflowTransition, WorkflowAction,
    WorkflowInstance, ApprovalHistory,
)
from app.domains.institution.models import (  # noqa: F401
    Institution, Campus, School, Department, Program, Branch, Semester,
)
from app.domains.notifications.models import Notification, DeviceToken  # noqa: F401
from app.domains.auth.models import User, Permission, Role, role_permissions, user_roles  # noqa: F401
from app.domains.fees.models import FeeDue, FeeStructure, FeeType, Payment  # noqa: F401
from app.domains.student.models import Student  # noqa: F401
from app.domains.academic_ops.models import (  # noqa: F401
    Room, TimeSlot, TimetableEntry, Substitution, ExamSchedule,
    GradingStructure, GradeRecord, Curriculum,
)
from app.domains.school_finance.models import (  # noqa: F401
    PaymentMethod, FeeSchedule, TransactionLog, PaymentReconciliation,
    ReconciliationItem, Receipt, FinanceReport,
)
from app.domains.report_builder.models import (  # noqa: F401
    ReportDefinition, SavedReport, ExportJob,
)
from app.domains.documents.models import (  # noqa: F401
    DocumentCategory, Document, DocumentVersion, DocumentShare,
)
from app.domains.communications.models import (  # noqa: F401
    CommunicationMessage, CommunicationPreference, MessageAttachment,
    MessageRecipient, MessageSchedule, MessageTemplate, MessageThread,
)
from app.domains.parent.models import Guardian  # noqa: F401
from app.domains.search.models import SearchHistory  # noqa: F401
from app.domains.student_portal.models import Assignment, AssignmentSubmission  # noqa: F401
from app.infrastructure.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

config.set_main_option("sqlalchemy.url", str(settings.database_url))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(
        str(settings.database_url),
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()