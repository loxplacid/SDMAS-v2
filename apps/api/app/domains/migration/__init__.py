# Import migrators to register them
from app.domains.migration import migrators  # noqa: F401
from app.domains.migration.base import BaseMigrator, MigratorResult
from app.domains.migration.discovery import (
    build_default_mapping,
    parse_source,
    profile_columns,
    suggest_mappings,
)
from app.domains.migration.engine import (
    MigrationEngine,
    get_migrator,
    get_registered_entity_types,
    register_migrator,
)
from app.domains.migration.import_job import (
    MIGRATION_IMPORT_JOB_TYPE,
    run_project_import,
)
from app.domains.migration.models import (
    MigrationLog,
    MigrationMapping,
    MigrationProject,
    MigrationRun,
)
from app.domains.migration.project_repository import MigrationProjectRepository
from app.domains.migration.project_service import MigrationProjectService
from app.domains.migration.readers import LegacyJSONReader
from app.domains.migration.reporting import build_summary, format_error_report, format_report_text
from app.domains.migration.rollback import RollbackService
from app.domains.migration.transforms import (
    TRANSFORM_REGISTRY,
    apply_mapping,
    apply_transforms,
)
from app.domains.migration.validators import (
    ValidationEngine,
    ValidationRule,
    max_length,
    one_of,
    positive_number,
    required,
    valid_email,
)

__all__ = [
    "BaseMigrator",
    "MigratorResult",
    "MigrationEngine",
    "get_migrator",
    "get_registered_entity_types",
    "register_migrator",
    "MigrationRun",
    "MigrationLog",
    "MigrationMapping",
    "MigrationProject",
    "MIGRATION_STATUSES",
    "MIGRATION_TRANSITIONS",
    "MigrationProjectService",
    "MigrationProjectRepository",
    "LegacyJSONReader",
    "build_summary",
    "format_error_report",
    "format_report_text",
    "RollbackService",
    "ValidationEngine",
    "ValidationRule",
    "required",
    "max_length",
    "one_of",
    "positive_number",
    "valid_email",
    "MigrationProjectService",
    "MigrationProjectRepository",
    "run_project_import",
    "MIGRATION_IMPORT_JOB_TYPE",
    "parse_source",
    "profile_columns",
    "suggest_mappings",
    "build_default_mapping",
    "apply_mapping",
    "apply_transforms",
    "TRANSFORM_REGISTRY",
]
