"""P15 — contextual communications tests.

* The template resolver is bounded: dot-notation variables only, no Python
  format specs, no attribute/index access, unknown paths render empty.
* Context variables are derived from real entities (student / fee due).
* Messages retain their operational context and audit it.
* Parent recipients are validated against the context student.
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.communications.context import (
    load_context_variables,
    load_context_summary,
    render_template_variables,
)
from app.domains.communications.schemas import MessageSend
from app.domains.communications.service import CommunicationService

# Register tables for the in-memory test DB (Base.metadata.create_all).
from app.domains.student.models import Student  # noqa: F401
from app.domains.academic.models import AcademicYear, Class, Enrollment, Section  # noqa: F401
from app.domains.fees.models import FeeDue  # noqa: F401
from app.domains.parent.models import Guardian  # noqa: F401 — registers guardian_links
from app.domains.communications.models import (  # noqa: F401
    CommunicationMessage,
    MessageRecipient,
    MessageTemplate,
)


# ── Bounded template resolver ──────────────────────────────────────────


class TestTemplateResolver:
    def test_resolves_dot_paths(self) -> None:
        out = render_template_variables(
            "Dear {student.name} of {student.class} (#{student.number})",
            {"student": {"name": "Amina", "class": "10A", "number": "S-100"}},
        )
        assert out == "Dear Amina of 10A (#S-100)"

    def test_unknown_and_dead_paths_render_empty(self) -> None:
        assert render_template_variables("{missing.key} x", {"other": "v"}) == " x"
        assert render_template_variables("{student.deep.path}", {"student": {"deep": "s"}}) == ""

    def test_attribute_access_is_never_honored(self) -> None:
        # ``__class__`` / ``__globals__``-style paths resolve against the
        # dict's own keys (which do not exist) — never against Python
        # object attributes.
        out = render_template_variables(
            "{student.__class__}", {"student": {"name": "x"}}
        )
        assert out == ""
        # Non-identifier placeholders (digit-prefixed) are not template
        # paths at all — they pass through untouched.
        out2 = render_template_variables(
            "{0.__class__}", {"0": "x"}
        )
        assert out2 == "{0.__class__}"

    def test_escapes_html_by_default(self) -> None:
        out = render_template_variables(
            "Hi {student.name}", {"student": {"name": "<b>&\"A\""}}
        )
        assert "&lt;b&gt;" in out and "&amp;" in out and "&quot;" in out

    def test_no_escape_for_plain_text(self) -> None:
        out = render_template_variables(
            "Hi {student.name}", {"student": {"name": "<b>"}}, escape=False
        )
        assert out == "Hi <b>"


# ── Context variable loading ───────────────────────────────────────────


async def _seed_student(db_session: AsyncSession) -> Student:
    student = Student(
        first_name="Rahul",
        last_name="Sharma",
        student_number="P15-001",
        email="rahul@test.local",
        campus_id=1,
        status="active",
    )
    db_session.add(student)
    await db_session.flush()
    return student


class TestContextVariables:
    async def test_student_context(self, db_session: AsyncSession) -> None:
        student = await _seed_student(db_session)
        variables = await load_context_variables(db_session, "student", student.id)
        st = variables["student"]
        assert st["name"] == "Rahul Sharma"
        assert st["number"] == "P15-001"
        assert st["email"] == "rahul@test.local"

    async def test_fee_due_context(self, db_session: AsyncSession) -> None:
        student = await _seed_student(db_session)
        due = FeeDue(
            student_id=student.id,
            academic_year_id=1,
            fee_structure_id=1,
            original_amount=50000,
            amount_paid=20000,
            due_date=datetime.date(2026, 9, 1),
            campus_id=1,
            status="partially_paid",
        )
        db_session.add(due)
        await db_session.flush()

        variables = await load_context_variables(db_session, "fee_due", due.id)
        fee = variables["fee"]
        assert fee["amount"] == 50000
        assert fee["paid"] == 20000
        assert fee["balance"] == 30000
        assert fee["due_date"] == "2026-09-01"

    async def test_unknown_context_raises(self, db_session: AsyncSession) -> None:
        from app.core.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            await load_context_variables(db_session, "planet", 1)


# ── Message context linking + parent validation ────────────────────────


async def _seed_user(db_session: AsyncSession, username: str, role: str) -> None:
    from app.domains.auth.models import User
    from app.domains.auth.security import hash_password

    user = User(
        username=username,
        email=f"{username}@test.local",
        display_name=username.title(),
        role=role,
        campus_id=1,
        is_active=True,
        password_hash=hash_password("Pass123!"),
    )
    db_session.add(user)
    await db_session.flush()


class TestMessageContext:
    async def test_message_stores_and_audits_context(self, db_session: AsyncSession) -> None:
        student = await _seed_student(db_session)
        await _seed_user(db_session, "sender", "staff")

        from app.domains.auth.models import User
        sender = (await db_session.execute(
            select(User).where(User.username == "sender")
        )).scalar_one()

        svc = CommunicationService(db_session)
        data = MessageSend(
            body="Fee reminder for {student.name}",
            message_type="targeted",
            channels=["in_app"],
            context_type="student",
            context_id=student.id,
            recipients=[{"recipient_type": "user", "recipient_id": sender.id}],
            variables={"student": {"name": f"{student.first_name} {student.last_name}"}},
        )
        msg = await svc.send_message(data, sender)

        assert msg.context_type == "student"
        assert msg.context_id == student.id

        import json

        from app.domains.audit.models import AuditLog
        logs = (await db_session.execute(
            select(AuditLog).where(AuditLog.resource_type == "communication_message")
        )).scalars().all()
        assert any(
            json.loads(log.details or "{}").get("context_type") == "student"
            and json.loads(log.details or "{}").get("context_id") == student.id
            for log in logs
        )

    async def test_list_messages_filters_by_context(
        self, db_session: AsyncSession
    ) -> None:
        """The sent-messages list can filter by operational context — this
        powers "communication history for this student / case / fee due"."""
        student = await _seed_student(db_session)
        await _seed_user(db_session, "sender_ctx", "staff")
        from app.domains.auth.models import User

        sender = (await db_session.execute(
            select(User).where(User.username == "sender_ctx")
        )).scalar_one()

        svc = CommunicationService(db_session)

        # Two messages linked to the student, one unlinked.
        for i in range(2):
            await svc.send_message(
                MessageSend(
                    body=f"Reminder {i}",
                    message_type="targeted",
                    channels=["in_app"],
                    context_type="student",
                    context_id=student.id,
                    recipients=[{"recipient_type": "user", "recipient_id": sender.id}],
                ),
                sender,
            )
        await svc.send_message(
            MessageSend(
                body="Plain announcement",
                message_type="announcement",
                channels=["in_app"],
            ),
            sender,
        )

        # Context filter returns only the linked messages.
        linked, linked_total = await svc.list_messages(
            user=sender, context_type="student", context_id=student.id
        )
        assert linked_total == 2
        assert all(m.context_type == "student" for m in linked)
        assert all(m.context_id == student.id for m in linked)

        # A different context id returns nothing.
        other, other_total = await svc.list_messages(
            user=sender, context_type="student", context_id=99999
        )
        assert other_total == 0

        # No context filter → all three messages.
        all_msgs, all_total = await svc.list_messages(user=sender)
        assert all_total == 3

    async def test_unlinked_message_has_null_context(self, db_session: AsyncSession) -> None:
        await _seed_user(db_session, "sender2", "staff")
        from app.domains.auth.models import User
        sender = (await db_session.execute(
            select(User).where(User.username == "sender2")
        )).scalar_one()

        svc = CommunicationService(db_session)
        data = MessageSend(
            body="Announcement",
            message_type="announcement",
            channels=["in_app"],
        )
        msg = await svc.send_message(data, sender)
        assert msg.context_type is None
        assert msg.context_id is None

    async def test_parent_recipient_must_be_guardian_of_context_student(
        self, db_session: AsyncSession
    ) -> None:
        student = await _seed_student(db_session)
        await _seed_user(db_session, "sender3", "staff")
        await _seed_user(db_session, "parent1", "parent")
        from app.domains.auth.models import User
        sender = (await db_session.execute(
            select(User).where(User.username == "sender3")
        )).scalar_one()
        parent = (await db_session.execute(
            select(User).where(User.username == "parent1")
        )).scalar_one()

        # A *different* parent (not linked to this student) — must be rejected.
        db_session.add(
            Guardian(
                user_id=parent.id,
                student_id=student.id + 1000,
                relationship="other",
            )
        )
        await db_session.flush()

        from app.core.exceptions import ValidationError
        svc = CommunicationService(db_session)
        data = MessageSend(
            body="Hello parent",
            message_type="targeted",
            channels=["in_app"],
            context_type="student",
            context_id=student.id,
            recipients=[{"recipient_type": "parent", "recipient_id": parent.id}],
        )
        with pytest.raises(ValidationError, match="not a guardian"):
            await svc.send_message(data, sender)

        # Now link the parent to THIS student — the same message must pass.
        db_session.add(
            Guardian(
                user_id=parent.id,
                student_id=student.id,
                relationship="father",
            )
        )
        await db_session.flush()
        ok_data = MessageSend(
            body="Hello parent",
            message_type="targeted",
            channels=["in_app"],
            context_type="student",
            context_id=student.id,
            recipients=[{"recipient_type": "parent", "recipient_id": parent.id}],
        )
        msg = await svc.send_message(ok_data, sender)
        assert msg.status in ("sent", "partial")

    async def test_context_summary_exposes_guardian_ids(
        self, db_session: AsyncSession
    ) -> None:
        student = await _seed_student(db_session)
        db_session.add(
            Guardian(
                user_id=42,
                student_id=student.id,
                relationship="father",
            )
        )
        await db_session.flush()

        summary = await load_context_summary(db_session, "student", student.id)
        assert summary["label"] == "Rahul Sharma"
        assert summary["variables"]["student"]["name"] == "Rahul Sharma"
        assert summary["guardian_ids"] == [42]


# ── Tenant scoping (IDOR guard) ────────────────────────────────────────


class TestContextTenantScoping:
    """The context loaders must refuse entities that belong to another
    campus when a tenant context is supplied (the router always supplies
    one via ``require_tenant_context``)."""

    async def test_cross_campus_student_is_denied(
        self, db_session: AsyncSession
    ) -> None:
        from app.core.exceptions import AuthorizationError
        from app.multi_tenant.models import TenantContext

        # Campus 2 student, caller scoped to campus 1.
        student = await _seed_student(db_session)
        student.campus_id = 2
        await db_session.flush()

        tenant = TenantContext(campus_id=1, institution_id=1, user_id=7)
        with pytest.raises(AuthorizationError, match="Cross-tenant access denied"):
            await load_context_variables(db_session, "student", student.id, tenant=tenant)
        with pytest.raises(AuthorizationError, match="Cross-tenant access denied"):
            await load_context_summary(db_session, "student", student.id, tenant=tenant)

    async def test_same_campus_student_is_allowed(
        self, db_session: AsyncSession
    ) -> None:
        from app.multi_tenant.models import TenantContext

        student = await _seed_student(db_session)  # campus_id=1
        tenant = TenantContext(campus_id=1, institution_id=1, user_id=7)

        variables = await load_context_variables(
            db_session, "student", student.id, tenant=tenant
        )
        assert variables["student"]["id"] == student.id

    async def test_cross_campus_fee_due_is_denied(
        self, db_session: AsyncSession
    ) -> None:
        from app.core.exceptions import AuthorizationError
        from app.multi_tenant.models import TenantContext

        student = await _seed_student(db_session)
        due = FeeDue(
            student_id=student.id,
            academic_year_id=1,
            fee_structure_id=1,
            original_amount=50000,
            amount_paid=0,
            due_date=datetime.date(2026, 9, 1),
            campus_id=2,
            status="unpaid",
        )
        db_session.add(due)
        await db_session.flush()

        tenant = TenantContext(campus_id=1, institution_id=1, user_id=7)
        with pytest.raises(AuthorizationError, match="Cross-tenant access denied"):
            await load_context_variables(db_session, "fee_due", due.id, tenant=tenant)
