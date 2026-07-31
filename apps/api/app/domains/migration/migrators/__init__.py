"""Registers all migrators on import."""
from app.domains.migration.migrators.users import UserMigrator
from app.domains.migration.migrators.students import StudentMigrator
from app.domains.migration.migrators.academic import AcademicMigrator
from app.domains.migration.migrators.attendance import AttendanceMigrator
from app.domains.migration.migrators.fees import FeeMigrator
