from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academic.models import Class, Enrollment
from app.domains.fees.models import FeeDue, Payment
from app.domains.report_builder.base import BaseReportBuilder, ReportMeta, ReportFilter, ReportColumn
from app.domains.report_builder.registry import ReportRegistry


@ReportRegistry.register
class FeeCollectionReport(BaseReportBuilder):
    @classmethod
    def meta(cls) -> ReportMeta:
        return ReportMeta(
            code="fee_collection",
            name="Fee Collection Report",
            description="Fee collection summary grouped by class with assigned, collected and outstanding amounts",
            category="fees",
            allowed_roles=["admin", "manager", "accountant"],
            filters=[
                ReportFilter(key="academic_year_id", label="Academic Year", type="select", required=True),
                ReportFilter(key="class_id", label="Class", type="select", required=False),
                ReportFilter(key="from_date", label="From Date", type="date", required=False),
                ReportFilter(key="to_date", label="To Date", type="date", required=False),
            ],
            columns=[
                ReportColumn(key="class_name", header="Class"),
                ReportColumn(key="total_assigned", header="Total Assigned", type="integer"),
                ReportColumn(key="total_collected", header="Total Collected", type="integer"),
                ReportColumn(key="total_outstanding", header="Total Outstanding", type="integer"),
                ReportColumn(key="collection_percentage", header="Collection %", type="number", format="0.00"),
                ReportColumn(key="student_count", header="Student Count", type="integer"),
            ],
        )

    async def fetch_data(
        self, params: dict[str, Any], user_id: int, campus_id: Optional[int], session: AsyncSession
    ) -> Any:
        academic_year_id = params["academic_year_id"]
        class_id = params.get("class_id")
        from_date = params.get("from_date")
        to_date = params.get("to_date")

        enroll_conditions = [Enrollment.academic_year_id == academic_year_id]
        if class_id is not None:
            enroll_conditions.append(Enrollment.class_id == class_id)
        if campus_id is not None:
            enroll_conditions.append(Enrollment.campus_id == campus_id)

        enroll_result = await session.execute(
            select(Enrollment).where(and_(*enroll_conditions))
        )
        enrollments = enroll_result.scalars().all()

        student_ids = {e.student_id for e in enrollments}
        class_ids = {e.class_id for e in enrollments if e.class_id is not None}

        classes = {}
        if class_ids:
            c_result = await session.execute(
                select(Class).where(Class.id.in_(class_ids))
            )
            classes = {c.id: c for c in c_result.scalars().all()}

        student_enroll_map: dict[int, list[Enrollment]] = {}
        for e in enrollments:
            student_enroll_map.setdefault(e.student_id, []).append(e)

        due_conditions = [FeeDue.academic_year_id == academic_year_id]
        if campus_id is not None:
            due_conditions.append(FeeDue.campus_id == campus_id)

        due_result = await session.execute(
            select(FeeDue).where(and_(*due_conditions))
        )
        all_dues = due_result.scalars().all()

        payment_conditions = []
        if from_date is not None:
            payment_conditions.append(Payment.payment_date >= from_date)
        if to_date is not None:
            payment_conditions.append(Payment.payment_date <= to_date)

        payment_query = select(Payment)
        if payment_conditions:
            payment_query = payment_query.where(and_(*payment_conditions))
        if campus_id is not None:
            payment_query = payment_query.where(Payment.campus_id == campus_id)

        payment_result = await session.execute(payment_query)
        all_payments = payment_result.scalars().all()

        payment_totals: dict[int, int] = {}
        for p in all_payments:
            payment_totals[p.student_id] = payment_totals.get(p.student_id, 0) + p.amount

        return {
            "enrollments": enrollments,
            "classes": classes,
            "student_enroll_map": student_enroll_map,
            "all_dues": all_dues,
            "payment_totals": payment_totals,
            "student_ids": student_ids,
        }

    def build_rows(self, data: Any) -> list[dict[str, Any]]:
        classes = data["classes"]
        student_enroll_map = data["student_enroll_map"]
        all_dues = data["all_dues"]
        payment_totals = data["payment_totals"]

        class_data: dict[int, dict] = {}
        for sid, enrolls in student_enroll_map.items():
            for e in enrolls:
                cid = e.class_id
                if cid is None:
                    continue
                if cid not in class_data:
                    class_data[cid] = {
                        "class_id": cid,
                        "student_ids": set(),
                        "total_assigned": 0,
                        "total_collected": 0,
                    }
                class_data[cid]["student_ids"].add(sid)

        for due in all_dues:
            for cid, cd in class_data.items():
                if due.student_id in cd["student_ids"]:
                    cd["total_assigned"] += due.original_amount

        for cid, cd in class_data.items():
            collected = 0
            for sid in cd["student_ids"]:
                collected += payment_totals.get(sid, 0)
            cd["total_collected"] = collected

        rows = []
        for cid, cd in class_data.items():
            cls = classes.get(cid)
            assigned = cd["total_assigned"]
            collected = cd["total_collected"]
            outstanding = assigned - collected
            pct = round((collected / assigned) * 100, 2) if assigned > 0 else 0.0

            rows.append({
                "class_name": cls.name if cls else "",
                "total_assigned": assigned,
                "total_collected": collected,
                "total_outstanding": outstanding,
                "collection_percentage": pct,
                "student_count": len(cd["student_ids"]),
            })

        rows.sort(key=lambda x: x["class_name"])
        return rows

    def build_summary(self, data: Any) -> dict[str, Any]:
        rows = self.build_rows(data)
        total_assigned = sum(r["total_assigned"] for r in rows)
        total_collected = sum(r["total_collected"] for r in rows)
        total_outstanding = sum(r["total_outstanding"] for r in rows)
        overall_pct = round((total_collected / total_assigned) * 100, 2) if total_assigned > 0 else 0.0

        return {
            "total_assigned": total_assigned,
            "total_collected": total_collected,
            "total_outstanding": total_outstanding,
            "collection_percentage": overall_pct,
        }
