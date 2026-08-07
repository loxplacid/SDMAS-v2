from __future__ import annotations

import datetime
import time
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academic.models import Class, Section, Subject, Teacher
from app.domains.academic_ops.models import GradeRecord
from app.domains.admission.models import AdmissionApplication
from app.domains.attendance.models import AttendanceRecord
from app.domains.auth.models import User
from app.domains.auth.permissions import (
    ACADEMIC_VIEW,
    ADMISSIONS_VIEW,
    ATTENDANCE_VIEW,
    FEES_VIEW,
    LEAVE_VIEW,
    NOTIFICATIONS_VIEW,
    STUDENTS_VIEW,
    TEACHERS_VIEW,
)
from app.domains.documents.models import Document
from app.domains.fees.models import FeeType, Payment
from app.domains.leave.models import LeaveRequest
from app.domains.notifications.models import Notification
from app.domains.school_finance.models import Receipt
from app.domains.search.models import SearchHistory
from app.domains.search.schemas import (
    GlobalSearchQuery,
    GlobalSearchResponse,
    GroupedSearchResult,
    SearchResultItem,
)
from app.domains.student.models import Student
from app.multi_tenant.models import TenantContext

ENTITY_TYPE_ORDER = [
    "student",
    "teacher",
    "class",
    "section",
    "fee",
    "payment",
    "notification",
    "document",
]

ENTITY_GROUP_LABELS: dict[str, str] = {
    "student": "Students",
    "teacher": "Teachers",
    "class": "Classes",
    "section": "Sections",
    "fee": "Fees",
    "payment": "Payments",
    "notification": "Notifications",
    "document": "Documents",
}

ENTITY_GROUP_ICONS: dict[str, str] = {
    "student": "M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z",
    "teacher": "M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z",
    "class": "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4",
    "section": "M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm0 8a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6z",
    "fee": "M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
    "payment": "M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z",
    "notification": "M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9",
    "document": "M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z",
}


@dataclass
class SearchEntityDef:
    entity_type: str
    model: type
    permission: str
    search_fields: list[tuple[str, float]]
    label_expr: str
    description_expr: str
    route_template: str
    id_field: str = "id"


# ---------------------------------------------------------------------------
# Local index sync (universal search)
# ---------------------------------------------------------------------------

# Entity types whose rows are mirrored into the browser-side FTS5 index.
# `permission` gates visibility; `changed_field` drives incremental sync.
# `route_template` formats the deep link (frontend route).
INDEX_ENTITY_TYPES: tuple[str, ...] = (
    "student",
    "teacher",
    "class",
    "section",
    "subject",
    "fee",
    "payment",
    "receipt",
    "notification",
    "document",
    "attendance",
    "grade_record",
    "leave_request",
    "admission_application",
)


@dataclass
class IndexEntityDef:
    entity_type: str
    model: type
    permission: str
    search_fields: list[tuple[str, float]]
    label_expr: str
    description_expr: str
    route_template: str
    id_field: str = "id"
    changed_field: str = "updated_at"




SEARCHABLE_ENTITIES: list[SearchEntityDef] = [
    SearchEntityDef(
        entity_type="student",
        model=Student,
        permission=STUDENTS_VIEW,
        search_fields=[
            ("first_name", 1.0),
            ("last_name", 1.0),
            ("student_number", 1.5),
            ("email", 0.8),
        ],
        label_expr="Student.first_name + ' ' + Student.last_name",
        description_expr="Student.student_number + ' • ' + Student.status",
        route_template="/students/{id}",
    ),
    SearchEntityDef(
        entity_type="teacher",
        model=Teacher,
        permission=TEACHERS_VIEW,
        search_fields=[
            ("first_name", 1.0),
            ("last_name", 1.0),
            ("employee_number", 1.5),
            ("email", 0.8),
        ],
        label_expr="Teacher.first_name + ' ' + Teacher.last_name",
        description_expr="Teacher.employee_number + ' • ' + Teacher.status",
        route_template="/teachers/{id}",
    ),
    SearchEntityDef(
        entity_type="class",
        model=Class,
        permission=ACADEMIC_VIEW,
        search_fields=[
            ("name", 1.0),
        ],
        label_expr="Class.name",
        description_expr="'Class'",
        route_template="/academic/classes",
    ),
    SearchEntityDef(
        entity_type="section",
        model=Section,
        permission=ACADEMIC_VIEW,
        search_fields=[
            ("name", 1.0),
        ],
        label_expr="Section.name",
        description_expr="'Section'",
        route_template="/academic/sections",
    ),
    SearchEntityDef(
        entity_type="fee",
        model=FeeType,
        permission=FEES_VIEW,
        search_fields=[
            ("name", 1.0),
            ("description", 0.6),
        ],
        label_expr="FeeType.name",
        description_expr="'Fee Type'",
        route_template="/fees/fee-types",
    ),
    SearchEntityDef(
        entity_type="payment",
        model=Payment,
        permission=FEES_VIEW,
        search_fields=[
            ("receipt_number", 1.5),
            ("payment_method", 0.6),
        ],
        label_expr="'Payment #' + Payment.receipt_number",
        description_expr="'Amount: ' + cast(Payment.amount, String)",
        route_template="/fees/payments",
    ),
    SearchEntityDef(
        entity_type="notification",
        model=Notification,
        permission=NOTIFICATIONS_VIEW,
        search_fields=[
            ("title", 1.0),
            ("message", 0.6),
        ],
        label_expr="Notification.title",
        description_expr="Notification.type",
        route_template="/notifications",
    ),
    SearchEntityDef(
        entity_type="document",
        model=Document,
        permission=STUDENTS_VIEW,
        search_fields=[
            ("original_filename", 1.0),
            ("title", 1.0),
            ("description", 0.6),
        ],
        label_expr="Document.original_filename",
        description_expr="Case(Document.title, else_='Document')",
        route_template="/operations",
    ),
]

# Reuse the search-field definitions; index definitions add a stable route and
# a changed-at column for incremental pulls. Attendance/leave/admission are
# capped by the client to recent rows (see sync protocol).
INDEXABLE_ENTITIES: dict[str, IndexEntityDef] = {
    defn.entity_type: IndexEntityDef(
        entity_type=defn.entity_type,
        model=defn.model,
        permission=defn.permission,
        search_fields=defn.search_fields,
        label_expr=defn.label_expr,
        description_expr=defn.description_expr,
        route_template=defn.route_template,
        id_field=defn.id_field,
    )
    for defn in SEARCHABLE_ENTITIES
}
INDEXABLE_ENTITIES.update(
    {
        "subject": IndexEntityDef(
            entity_type="subject",
            model=Subject,
            permission=ACADEMIC_VIEW,
            search_fields=[("name", 1.0), ("code", 1.2)],
            label_expr="Subject.name",
            description_expr="Subject.code if Subject.code else 'Subject'",
            route_template="/subjects",
        ),
        "receipt": IndexEntityDef(
            entity_type="receipt",
            model=Receipt,
            permission=FEES_VIEW,
            search_fields=[("receipt_number", 1.5), ("payment_method_name", 0.4)],
            label_expr="'Receipt #' + Receipt.receipt_number",
            description_expr="'Amount: ' + cast(Receipt.amount, String)",
            route_template="/fees/payments",
        ),
        "attendance": IndexEntityDef(
            entity_type="attendance",
            model=AttendanceRecord,
            permission=ATTENDANCE_VIEW,
            search_fields=[("attendance_date", 1.0), ("status", 0.8), ("notes", 0.4)],
            label_expr="'Attendance ' + AttendanceRecord.attendance_date",
            description_expr="'Record #' + cast(AttendanceRecord.id, String) + ' • ' + AttendanceRecord.status",
            route_template="/attendance/records/{id}",
        ),
        "grade_record": IndexEntityDef(
            entity_type="grade_record",
            model=GradeRecord,
            permission=ACADEMIC_VIEW,
            search_fields=[("marks_obtained", 0.6), ("grade", 0.8), ("remarks", 0.4)],
            label_expr="'Grade #' + cast(GradeRecord.id, String)",
            description_expr="'Marks: ' + cast(GradeRecord.marks_obtained, String) + ' • Grade ' + GradeRecord.grade",
            route_template="/academic/classes",
        ),
        "leave_request": IndexEntityDef(
            entity_type="leave_request",
            model=LeaveRequest,
            permission=LEAVE_VIEW,
            search_fields=[("reason", 0.8), ("leave_type", 0.8)],
            label_expr="'Leave #' + cast(LeaveRequest.id, String) + ' (' + LeaveRequest.leave_type + ')'",
            description_expr="LeaveRequest.reason",
            route_template="/leave",
        ),
        "admission_application": IndexEntityDef(
            entity_type="admission_application",
            model=AdmissionApplication,
            permission=ADMISSIONS_VIEW,
            search_fields=[("applicant_name", 1.0), ("email", 0.8), ("phone", 0.6)],
            label_expr="AdmissionApplication.applicant_name",
            description_expr="'Admission • ' + AdmissionApplication.status",
            route_template="/admissions/{id}",
        ),
    }
)




class SearchService:
    def __init__(
        self,
        session: AsyncSession,
        current_user: User,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        self.session = session
        self.current_user = current_user
        self.tenant = tenant
        self.role_codes = current_user.role_codes

    async def _get_permissions(self) -> set[str]:
        from app.domains.auth.permission_service import PermissionService

        svc = PermissionService(self.session)
        all_perms: set[str] = set()
        for role_code in self.role_codes:
            perms = await svc.get_role_permissions(role_code)
            all_perms.update(perms)
        return all_perms

    async def global_search(
        self, params: GlobalSearchQuery
    ) -> GlobalSearchResponse:
        start = time.monotonic()
        query = params.query.strip()
        allowed_types = set(params.types) if params.types else None
        user_permissions = await self._get_permissions()

        all_results: list[SearchResultItem] = []

        for entity_def in SEARCHABLE_ENTITIES:
            if allowed_types and entity_def.entity_type not in allowed_types:
                continue
            if entity_def.permission not in user_permissions:
                continue

            results = await self._search_entity(query, entity_def)
            all_results.extend(results)

        all_results.sort(key=lambda r: r.score or 0, reverse=True)

        total = len(all_results)
        offset = (params.page - 1) * params.size
        page_results = all_results[offset : offset + params.size]

        grouped = self._build_grouped(page_results)

        await self._save_search_history(query, params.types, total)

        elapsed = (time.monotonic() - start) * 1000

        return GlobalSearchResponse(
            query=query,
            total=total,
            page=params.page,
            size=params.size,
            results=page_results,
            grouped=grouped,
            took_ms=round(elapsed, 1),
        )

    def _build_grouped(
        self, results: list[SearchResultItem]
    ) -> list[GroupedSearchResult]:
        groups: dict[str, list[SearchResultItem]] = {}
        for r in results:
            groups.setdefault(r.entity_type, []).append(r)

        result: list[GroupedSearchResult] = []
        for etype in ENTITY_TYPE_ORDER:
            if etype in groups:
                result.append(
                    GroupedSearchResult(
                        entity_type=etype,
                        label=ENTITY_GROUP_LABELS.get(etype, etype.title()),
                        icon=ENTITY_GROUP_ICONS.get(etype, ""),
                        items=groups[etype],
                    )
                )
        return result

    async def _search_entity(
        self, query: str, entity_def: SearchEntityDef
    ) -> list[SearchResultItem]:
        model = entity_def.model
        like_term = f"%{query}%"

        conditions = []
        for field_name, _weight in entity_def.search_fields:
            field = getattr(model, field_name, None)
            if field is not None:
                conditions.append(field.ilike(like_term))

        if not conditions:
            return []

        where_clause = conditions[0]
        for c in conditions[1:]:
            where_clause = where_clause | c

        if self.tenant and self.tenant.campus_id is not None:
            if hasattr(model, "campus_id"):
                where_clause = where_clause & (
                    getattr(model, "campus_id") == self.tenant.campus_id
                )

        stmt = (
            select(model).where(where_clause).order_by(model.id).limit(20)
        )

        db_results = await self.session.execute(stmt)
        rows = db_results.scalars().all()

        results: list[SearchResultItem] = []
        for row in rows:
            label = self._resolve_label(entity_def, row)
            description = self._resolve_description(entity_def, row)
            entity_id = int(getattr(row, entity_def.id_field))
            match_field = self._find_match_field(query, entity_def, row)
            score = self._compute_score(query, entity_def, row)

            route = entity_def.route_template.format(
                id=entity_id,
                student_id=entity_id,
                teacher_id=entity_id,
            )

            results.append(
                SearchResultItem(
                    id=f"{entity_def.entity_type}-{entity_id}",
                    entity_type=entity_def.entity_type,
                    entity_id=entity_id,
                    label=label,
                    description=description,
                    route=route,
                    match_field=match_field,
                    score=score,
                )
            )

        return results

    def _resolve_label(
        self, entity_def: SearchEntityDef, row: Any
    ) -> str:
        if entity_def.entity_type == "student":
            return f"{row.first_name} {row.last_name}"
        elif entity_def.entity_type == "teacher":
            return f"{row.first_name} {row.last_name}"
        elif entity_def.entity_type == "payment":
            return f"Payment #{row.receipt_number or row.id}"
        elif entity_def.entity_type == "receipt":
            return f"Receipt #{row.receipt_number}"
        elif entity_def.entity_type == "document":
            return row.original_filename
        elif entity_def.entity_type == "notification":
            return row.title
        elif entity_def.entity_type == "subject":
            return f"{row.name} ({row.code})"
        elif entity_def.entity_type == "attendance":
            return f"Attendance {row.attendance_date}"
        elif entity_def.entity_type == "grade_record":
            return f"Grade #{row.id}"
        elif entity_def.entity_type == "leave_request":
            return f"Leave #{row.id} ({row.leave_type})"
        elif entity_def.entity_type == "admission_application":
            return row.applicant_name
        return str(getattr(row, "name", ""))

    def _resolve_description(
        self, entity_def: SearchEntityDef, row: Any
    ) -> str:
        if entity_def.entity_type == "student":
            return f"{row.student_number} • {row.status}"
        elif entity_def.entity_type == "teacher":
            return f"{row.employee_number} • {row.status}"
        elif entity_def.entity_type == "class":
            return "Class"
        elif entity_def.entity_type == "section":
            return "Section"
        elif entity_def.entity_type == "fee":
            return "Fee Type"
        elif entity_def.entity_type == "payment":
            return f"Amount: {row.amount} • {row.payment_method or 'N/A'}"
        elif entity_def.entity_type == "receipt":
            return f"Amount: {row.amount} • {row.payment_method_name or 'N/A'}"
        elif entity_def.entity_type == "notification":
            return f"{row.type} • {getattr(row, 'is_read', False) and 'Read' or 'Unread'}"
        elif entity_def.entity_type == "document":
            return row.title or "Document"
        elif entity_def.entity_type == "subject":
            return "Subject"
        elif entity_def.entity_type == "attendance":
            return f"Record #{row.id} • {row.status}"
        elif entity_def.entity_type == "grade_record":
            return f"Marks: {row.marks_obtained} • Grade {row.grade}"
        elif entity_def.entity_type == "leave_request":
            return row.reason or "Leave request"
        elif entity_def.entity_type == "admission_application":
            return f"Admission • {row.status}"
        return ""

    def _find_match_field(
        self, query: str, entity_def: SearchEntityDef, row: Any
    ) -> str | None:
        query_lower = query.lower()
        for field_name, _weight in entity_def.search_fields:
            value = getattr(row, field_name, None)
            if value and isinstance(value, str) and query_lower in value.lower():
                return field_name
        return None

    def _compute_score(
        self, query: str, entity_def: SearchEntityDef, row: Any
    ) -> float:
        query_lower = query.lower()
        score = 0.0
        for field_name, weight in entity_def.search_fields:
            value = getattr(row, field_name, None)
            if value and isinstance(value, str):
                val_lower = value.lower()
                if val_lower == query_lower:
                    score += 2.0 * weight
                elif val_lower.startswith(query_lower):
                    score += 1.5 * weight
                elif query_lower in val_lower:
                    score += 1.0 * weight
        return round(score, 4)

    async def _save_search_history(
        self,
        query: str,
        types: list[str] | None,
        result_count: int,
    ) -> None:
        history = SearchHistory(
            user_id=self.current_user.id,
            query=query[:500],
            entity_type=",".join(types) if types else None,
            result_count=result_count,
            campus_id=self.tenant.campus_id if self.tenant else None,
        )
        self.session.add(history)

    async def get_recent_searches(
        self, limit: int = 10
    ) -> list[SearchHistory]:
        stmt = (
            select(SearchHistory)
            .where(SearchHistory.user_id == self.current_user.id)
            .order_by(SearchHistory.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_search_history(self, search_id: int | None = None) -> None:
        if search_id is not None:
            stmt = delete(SearchHistory).where(
                SearchHistory.id == search_id,
                SearchHistory.user_id == self.current_user.id,
            )
        else:
            stmt = delete(SearchHistory).where(
                SearchHistory.user_id == self.current_user.id
            )
        await self.session.execute(stmt)

    async def get_frequent_searches(self, limit: int = 5) -> list[tuple[str, int]]:
        stmt = (
            select(SearchHistory.query, func.count(SearchHistory.id).label("cnt"))
            .where(SearchHistory.user_id == self.current_user.id)
            .group_by(SearchHistory.query)
            .order_by(text("cnt DESC"))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    # ------------------------------------------------------------------
    # Local index sync (universal search)
    # ------------------------------------------------------------------
    # The browser mirrors a permission-scoped projection of the entity
    # tables into a local SQLite FTS5 index. The sync protocol:
    #   1. client requests page 0 of an entity type
    #   2. server returns up to `size` rows ordered by `changed_field`
    #   3. client stores `cursor` = max changed_at seen; requests `page+1`
    #   4. when `has_more` is false, the type is caught up
    # Subsequent runs pass `since` (the stored cursor) so only rows
    # modified after the last sync are returned — incremental.
    # ------------------------------------------------------------------

    async def _allowed_entity_types(self) -> list[str]:
        user_permissions = await self._get_permissions()
        return [
            etype
            for etype in INDEX_ENTITY_TYPES
            if etype in INDEXABLE_ENTITIES
            and INDEXABLE_ENTITIES[etype].permission in user_permissions
        ]

    async def sync_index(
        self,
        entity_type: str,
        page: int = 0,
        size: int = 200,
        since: Optional[str] = None,
    ) -> dict:
        """Return index rows for one entity type, permission-scoped.

        The first page (page=0) returns the most recently changed rows
        (``changed_field`` DESC) so the client gets a useful subset fast;
        pass ``since`` to restrict to rows modified after a timestamp.
        """
        allowed = await self._allowed_entity_types()
        if entity_type not in allowed or entity_type not in INDEXABLE_ENTITIES:
            return {"entity_type": entity_type, "items": [], "has_more": False}

        entity_def = INDEXABLE_ENTITIES[entity_type]
        model = entity_def.model
        changed_col = getattr(model, entity_def.changed_field, None)
        if changed_col is None:
            changed_col = getattr(model, "created_at")

        conditions: list = []
        if since:
            try:
                conditions.append(changed_col > datetime.datetime.fromisoformat(since))
            except ValueError:
                pass
        if self.tenant and self.tenant.campus_id is not None:
            if hasattr(model, "campus_id"):
                conditions.append(getattr(model, "campus_id") == self.tenant.campus_id)

        # page 0 = newest first (fast useful subset); deeper pages keep the
        # same ordering so pagination is stable.
        stmt = select(model).where(*conditions).order_by(
            changed_col.desc(), model.id.desc()
        ).limit(size).offset(page * size)

        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        items = [self._index_row(entity_type, entity_def, row, changed_col) for row in rows]
        return {
            "entity_type": entity_type,
            "items": items,
            "has_more": len(rows) == size,
        }

    def _index_row(
        self,
        entity_type: str,
        entity_def: IndexEntityDef,
        row: Any,
        changed_col,
    ) -> dict:
        entity_id = int(getattr(row, entity_def.id_field))
        label = self._resolve_label(entity_def, row)
        description = self._resolve_description(entity_def, row)
        changed_at = getattr(row, entity_def.changed_field, None)
        if changed_at is None:
            changed_at = getattr(row, "created_at", None)

        search_parts: list[str] = []
        for field_name, _weight in entity_def.search_fields:
            value = getattr(row, field_name, None)
            if value is not None:
                search_parts.append(str(value))

        route = entity_def.route_template.format(
            id=entity_id,
            student_id=entity_id,
            teacher_id=entity_id,
        )

        return {
            "id": f"{entity_type}-{entity_id}",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "label": label,
            "description": description,
            "route": route,
            "search_text": " ".join(search_parts),
            "changed_at": (
                changed_at.isoformat() if changed_at is not None else None
            ),
        }
