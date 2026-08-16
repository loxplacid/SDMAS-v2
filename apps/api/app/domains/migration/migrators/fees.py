from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import select

from app.domains.fees.models import FeeDue, FeeStructure, FeeType, Payment
from app.domains.migration.base import BaseMigrator, MigratorResult
from app.domains.migration.engine import register_migrator
from app.domains.migration.validators import ValidationRule, max_length, positive_number, required


@register_migrator
class FeeMigrator(BaseMigrator):
    """Migrates fee structure: fee_types, fee_structures, fee_dues, payments.

    Expects list-of-dicts where each dict has keys::

        {"fee_types": [...], "fee_structures": [...],
         "fee_dues": [...], "payments": [...]}
    """

    entity_type = "fees"
    dependencies = ["students", "academic"]

    async def validate(
        self,
        records: list[dict[str, Any]],
        session: Any,
        run_id: int,
        log_repo: Any,
    ) -> list[dict[str, Any]]:
        return records

    async def migrate(
        self,
        records: list[dict[str, Any]],
        session: Any,
        run_id: int,
        mapping_repo: Any,
        log_repo: Any,
    ) -> MigratorResult:
        result = MigratorResult(entity_type="fees", total=len(records))

        for container in records:
            for rec in container.get("fee_types", []):
                await self._import_fee_type(rec, session, run_id, mapping_repo, log_repo, result)
            for rec in container.get("fee_structures", []):
                await self._import_fee_structure(rec, session, run_id, mapping_repo, log_repo, result)
            for rec in container.get("fee_dues", []):
                await self._import_fee_due(rec, session, run_id, mapping_repo, log_repo, result)
            for rec in container.get("payments", []):
                await self._import_payment(rec, session, run_id, mapping_repo, log_repo, result)

        return result

    async def rollback(self, run_id, session, mapping_repo):
        """Delete every fee row this run created, in FK-safe order.

        The fee migrator records mappings per *subtype* (``fee_type``,
        ``fee_structure``, ``fee_due``, ``payment``) — the base rollback
        looks them up by run entity type (``fees``) and finds nothing.
        Group the run's whole mapping set by subtype and delete
        children-first: payments → fee_dues → fee_structures → fee_types.
        """
        from sqlalchemy import delete

        mappings = await mapping_repo.list_by_run(run_id)
        by_type: dict[str, list[int]] = {}
        for m in mappings:
            by_type.setdefault(m.entity_type, []).append(m.sdmas_id)

        table_by_type = [
            ("payment", Payment),
            ("fee_due", FeeDue),
            ("fee_structure", FeeStructure),
            ("fee_type", FeeType),
        ]
        total = 0
        for entity_type, model in table_by_type:
            ids = by_type.get(entity_type)
            if not ids:
                continue
            result = await session.execute(delete(model).where(model.id.in_(ids)))
            total += result.rowcount
        await session.flush()
        return total

    async def _import_fee_type(self, rec, session, run_id, mapping_repo, log_repo, result):
        lid = str(rec.get("legacy_id", ""))
        try:
            name = rec.get("name", "")
            existing = await session.execute(
                select(FeeType).where(FeeType.name == name)
            )
            if existing.scalar_one_or_none() is not None:
                result.skipped += 1
                await log_repo.log(run_id, "skipped", "fees", lid, "fee_type",
                                   f"FeeType '{name}' already exists")
                return

            entity = FeeType(
                name=name,
                description=rec.get("description"),
                campus_id=rec.get("campus_id"),
                status=rec.get("status", "active"),
                created_at=datetime.datetime.now(datetime.timezone.utc),
                updated_at=datetime.datetime.now(datetime.timezone.utc),
            )
            session.add(entity)
            await session.flush()
            await mapping_repo.record(run_id, "fee_type", lid, entity.id)
            result.imported += 1
            await log_repo.log(run_id, "imported", "fees", lid, "fee_type",
                               f"FeeType '{name}' imported as ID {entity.id}")
        except Exception as exc:
            result.errors += 1
            result.error_details.append({"legacy_id": lid, "subtype": "fee_type", "error": str(exc)})
            await log_repo.log(run_id, "error", "fees", lid, "fee_type", f"Failed: {exc}")

    async def _import_fee_structure(self, rec, session, run_id, mapping_repo, log_repo, result):
        lid = str(rec.get("legacy_id", ""))
        try:
            entity = FeeStructure(
                academic_year_id=rec.get("academic_year_id"),
                class_id=rec.get("class_id"),
                fee_type_id=rec.get("fee_type_id"),
                amount=rec.get("amount", 0),
                frequency=rec.get("frequency", "annual"),
                campus_id=rec.get("campus_id"),
                status=rec.get("status", "active"),
                created_at=datetime.datetime.now(datetime.timezone.utc),
                updated_at=datetime.datetime.now(datetime.timezone.utc),
            )
            session.add(entity)
            await session.flush()
            await mapping_repo.record(run_id, "fee_structure", lid, entity.id)
            result.imported += 1
            await log_repo.log(run_id, "imported", "fees", lid, "fee_structure",
                               f"FeeStructure imported as ID {entity.id}")
        except Exception as exc:
            result.errors += 1
            result.error_details.append({"legacy_id": lid, "subtype": "fee_structure", "error": str(exc)})
            await log_repo.log(run_id, "error", "fees", lid, "fee_structure", f"Failed: {exc}")

    async def _import_fee_due(self, rec, session, run_id, mapping_repo, log_repo, result):
        lid = str(rec.get("legacy_id", ""))
        try:
            entity = FeeDue(
                student_id=rec.get("student_id"),
                academic_year_id=rec.get("academic_year_id"),
                fee_structure_id=rec.get("fee_structure_id"),
                original_amount=rec.get("original_amount", 0),
                amount_paid=rec.get("amount_paid", 0),
                due_date=str(rec.get("due_date", "")),
                campus_id=rec.get("campus_id"),
                status=rec.get("status", "unpaid"),
                created_at=datetime.datetime.now(datetime.timezone.utc),
                updated_at=datetime.datetime.now(datetime.timezone.utc),
            )
            session.add(entity)
            await session.flush()
            await mapping_repo.record(run_id, "fee_due", lid, entity.id)
            result.imported += 1
            await log_repo.log(run_id, "imported", "fees", lid, "fee_due",
                               f"FeeDue imported as ID {entity.id}")
        except Exception as exc:
            result.errors += 1
            result.error_details.append({"legacy_id": lid, "subtype": "fee_due", "error": str(exc)})
            await log_repo.log(run_id, "error", "fees", lid, "fee_due", f"Failed: {exc}")

    async def _import_payment(self, rec, session, run_id, mapping_repo, log_repo, result):
        lid = str(rec.get("legacy_id", ""))
        try:
            receipt = rec.get("receipt_number")
            if receipt:
                existing = await session.execute(
                    select(Payment).where(Payment.receipt_number == receipt)
                )
                if existing.scalar_one_or_none() is not None:
                    result.skipped += 1
                    await log_repo.log(run_id, "skipped", "fees", lid, "payment",
                                       f"Payment with receipt '{receipt}' already exists")
                    return

            entity = Payment(
                student_id=rec.get("student_id"),
                fee_due_id=rec.get("fee_due_id"),
                amount=rec.get("amount", 0),
                payment_date=str(rec.get("payment_date", "")),
                payment_method=rec.get("payment_method"),
                receipt_number=receipt,
                campus_id=rec.get("campus_id"),
                created_at=datetime.datetime.now(datetime.timezone.utc),
            )
            session.add(entity)
            await session.flush()
            # Track the payment in the run's mapping table so rollback can
            # remove it (payments reference fee_dues, so they must be
            # deleted before the dues they point at).
            await mapping_repo.record(run_id, "payment", lid, entity.id)
            result.imported += 1
            await log_repo.log(run_id, "imported", "fees", lid, "payment",
                               f"Payment imported as SDMAS ID {entity.id}")
        except Exception as exc:
            result.errors += 1
            result.error_details.append({"legacy_id": lid, "subtype": "payment", "error": str(exc)})
            await log_repo.log(run_id, "error", "fees", lid, "payment", f"Failed: {exc}")
