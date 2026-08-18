from __future__ import annotations

import datetime
from typing import Any

from app.domains.auth.models import User
from app.domains.auth.security import hash_password
from app.domains.migration.base import BaseMigrator, MigratorResult
from app.domains.migration.engine import register_migrator
from app.domains.migration.validators import (
    ValidationRule,
    max_length,
    one_of,
    required,
    valid_email,
)


@register_migrator
class UserMigrator(BaseMigrator):
    """Migrates users from the legacy system.

    Expects records with fields:
        legacy_id, email, username, display_name, role, is_active,
        campus_id (optional)
    """

    entity_type = "users"
    table_name = "users"
    dependencies: list[str] = []

    def _rules(self) -> list[ValidationRule]:
        return [
            required("email"),
            required("username"),
            required("display_name"),
            valid_email("email"),
            max_length("email", 255),
            max_length("username", 100),
            max_length("display_name", 200),
            one_of("role", {"admin", "staff", "teacher", "student", "parent"}),
        ]

    async def validate(
        self,
        records: list[dict[str, Any]],
        session: Any,
        run_id: int,
        log_repo: Any,
    ) -> list[dict[str, Any]]:
        from app.domains.migration.validators import ValidationEngine

        engine = ValidationEngine()
        engine.add_rules("users", self._rules())
        validated: list[dict[str, Any]] = []
        for record, result in engine.validate("users", records):
            if result.is_valid:
                validated.append(record)
            else:
                await log_repo.log(
                    run_id=run_id,
                    level="error",
                    entity_type="users",
                    legacy_id=record.get("legacy_id"),
                    message="Validation failed",
                    details={"errors": result.errors},
                )
        return validated

    async def migrate(
        self,
        records: list[dict[str, Any]],
        session: Any,
        run_id: int,
        mapping_repo: Any,
        log_repo: Any,
    ) -> MigratorResult:
        result = MigratorResult(entity_type="users", total=len(records))

        for record in records:
            legacy_id = str(record.get("legacy_id", ""))
            email = record.get("email", "")
            username = record.get("username", "")

            try:
                existing = await session.execute(
                    __import__("sqlalchemy")
                    .select(User)
                    .where((User.email == email) | (User.username == username))
                )
                if existing.scalar_one_or_none() is not None:
                    result.skipped += 1
                    await log_repo.log(
                        run_id=run_id,
                        level="skipped",
                        entity_type="users",
                        legacy_id=legacy_id,
                        message=f"User '{email}' already exists — skipped",
                    )
                    continue

                default_password = record.get("default_password", "Welcome@123")
                user = User(
                    email=email,
                    username=username,
                    password_hash=hash_password(default_password),
                    display_name=record.get("display_name", username),
                    role=record.get("role", "staff"),
                    is_active=record.get("is_active", True),
                    campus_id=record.get("campus_id"),
                    created_at=datetime.datetime.now(datetime.timezone.utc),
                    updated_at=datetime.datetime.now(datetime.timezone.utc),
                )
                session.add(user)
                await session.flush()

                await mapping_repo.record(run_id, "users", legacy_id, user.id)
                result.imported += 1
                await log_repo.log(
                    run_id=run_id,
                    level="imported",
                    entity_type="users",
                    legacy_id=legacy_id,
                    message=f"User '{email}' imported as SDMAS ID {user.id}",
                )
            except Exception as exc:
                result.errors += 1
                result.error_details.append(
                    {
                        "legacy_id": legacy_id,
                        "email": email,
                        "error": str(exc),
                    }
                )
                await log_repo.log(
                    run_id=run_id,
                    level="error",
                    entity_type="users",
                    legacy_id=legacy_id,
                    message=f"Failed to import user: {exc}",
                    details={"error": str(exc)},
                )

        return result
