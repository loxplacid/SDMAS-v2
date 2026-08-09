from __future__ import annotations

import datetime
from typing import Any, Optional, Sequence

from sqlalchemy import func, select, or_, and_, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.domains.auth.models import User
from app.domains.communications.constants import (
    ALL_CHANNELS,
    CHANNEL_IN_APP,
    MESSAGE_TYPES,
    MSG_TYPE_ANNOUNCEMENT,
    MSG_TYPE_CLASS,
    MSG_TYPE_SECTION,
    MSG_TYPE_TARGETED,
    MSG_TYPE_PARENT,
    MSG_TYPE_TEACHER,
    MSG_TYPE_STAFF,
    PRIORITY_NORMAL,
    PRIORITY_HIGH,
    PRIORITY_URGENT,
    RECIPIENT_STATUS_PENDING,
    RECIPIENT_STATUS_SENT,
    RECIPIENT_STATUS_DELIVERED,
    RECIPIENT_STATUS_FAILED,
    RECIPIENT_STATUS_READ,
    RECIPIENT_TYPE_USER,
    RECIPIENT_TYPE_STUDENT,
    RECIPIENT_TYPE_TEACHER,
    RECIPIENT_TYPE_PARENT,
    RECURRENCE_NONE,
    SCHEDULE_STATUS_PENDING,
    SCHEDULE_STATUS_SENDING,
    SCHEDULE_STATUS_COMPLETED,
    SCHEDULE_STATUS_FAILED,
    STATUS_DRAFT,
    STATUS_SENT,
    STATUS_SCHEDULED,
    STATUS_FAILED,
    STATUS_PARTIAL,
)
from app.domains.communications.context import (
    load_context_summary,
    load_context_variables,
    render_template_variables,
)
from app.domains.communications.models import (
    CommunicationMessage,
    CommunicationPreference,
    MessageAttachment,
    MessageRecipient,
    MessageSchedule,
    MessageTemplate,
    MessageThread,
)
from app.domains.communications.providers import ProviderFactory, ProviderMessage


class MessageTemplateService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: Any, user: User) -> MessageTemplate:
        tpl = MessageTemplate(
            code=data.code,
            name=data.name,
            subject=data.subject,
            body=data.body,
            message_type=data.message_type,
            channels=data.channels,
            variables=data.variables,
            campus_id=getattr(user, "campus_id", None),
            created_by=user.id,
        )
        self.session.add(tpl)
        await self.session.commit()
        await self.session.refresh(tpl)
        return tpl

    async def list(self, skip: int = 0, limit: int = 20) -> tuple[Sequence[MessageTemplate], int]:
        query = select(MessageTemplate).offset(skip).limit(limit).order_by(MessageTemplate.name)
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        count_result = await self.session.execute(select(func.count(MessageTemplate.id)))
        total = count_result.scalar() or 0
        return items, total

    async def get(self, template_id: int) -> MessageTemplate:
        tpl = await self.session.get(MessageTemplate, template_id)
        if not tpl:
            raise NotFoundError("Message template not found")
        return tpl

    async def get_by_code(self, code: str) -> MessageTemplate:
        result = await self.session.execute(
            select(MessageTemplate).where(MessageTemplate.code == code)
        )
        tpl = result.scalar_one_or_none()
        if not tpl:
            raise NotFoundError(f"Template '{code}' not found")
        return tpl

    async def update(self, template_id: int, data: Any) -> MessageTemplate:
        tpl = await self.get(template_id)
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(tpl, key, value)
        await self.session.commit()
        await self.session.refresh(tpl)
        return tpl

    async def delete(self, template_id: int) -> None:
        tpl = await self.get(template_id)
        await self.session.delete(tpl)
        await self.session.commit()

    async def render(self, template_id: int, variables: dict[str, Any]) -> dict[str, str]:
        """Render a template with the P15 bounded variable resolver.

        Only ``{name}`` / ``{name.path}`` placeholders are substituted — no
        Python format specs, no attribute access, no arbitrary code.
        """
        tpl = await self.get(template_id)
        subject = render_template_variables(tpl.subject, variables, escape=True) if tpl.subject else None
        body = render_template_variables(tpl.body, variables, escape=True)
        return {"subject": subject or "", "body": body}


class RecipientResolver:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve(
        self,
        recipients: Optional[list[dict]] = None,
        class_ids: Optional[list[int]] = None,
        section_ids: Optional[list[int]] = None,
    ) -> list[dict[str, Any]]:
        resolved: list[dict[str, Any]] = []

        if recipients:
            for r in recipients:
                resolved.append({
                    "recipient_type": r["recipient_type"],
                    "recipient_id": r["recipient_id"],
                })

        if class_ids:
            from app.domains.academic.models import Enrollment
            result = await self.session.execute(
                select(Enrollment.student_id).where(
                    Enrollment.class_id.in_(class_ids),
                    Enrollment.status == "active",
                )
            )
            for (student_id,) in result.all():
                resolved.append({
                    "recipient_type": RECIPIENT_TYPE_STUDENT,
                    "recipient_id": student_id,
                })

        if section_ids:
            from app.domains.academic.models import Enrollment
            result = await self.session.execute(
                select(Enrollment.student_id).where(
                    Enrollment.section_id.in_(section_ids),
                    Enrollment.status == "active",
                )
            )
            for (student_id,) in result.all():
                resolved.append({
                    "recipient_type": RECIPIENT_TYPE_STUDENT,
                    "recipient_id": student_id,
                })

        seen = {(r["recipient_type"], r["recipient_id"]) for r in resolved}
        return [{"recipient_type": t, "recipient_id": i} for t, i in seen]

    async def resolve_with_details(
        self,
        recipients: Optional[list[dict]] = None,
        class_ids: Optional[list[int]] = None,
        section_ids: Optional[list[int]] = None,
    ) -> list[dict[str, Any]]:
        raw = await self.resolve(recipients, class_ids, section_ids)
        result: list[dict[str, Any]] = []

        student_ids = [r["recipient_id"] for r in raw if r["recipient_type"] == RECIPIENT_TYPE_STUDENT]
        user_ids = [r["recipient_id"] for r in raw if r["recipient_type"] == RECIPIENT_TYPE_USER]

        students_map = {}
        users_map = {}

        if student_ids:
            from app.domains.student.models import Student
            rows = await self.session.execute(
                select(Student).where(Student.id.in_(student_ids))
            )
            for s in rows.scalars().all():
                students_map[s.id] = {
                    "id": s.id,
                    "name": f"{s.first_name} {s.last_name}",
                    "email": s.email,
                }

        if user_ids:
            rows = await self.session.execute(
                select(User).where(User.id.in_(user_ids))
            )
            for u in rows.scalars().all():
                users_map[u.id] = {
                    "id": u.id,
                    "name": u.display_name,
                    "email": u.email,
                }

        for r in raw:
            details = {}
            if r["recipient_type"] == RECIPIENT_TYPE_STUDENT:
                details = students_map.get(r["recipient_id"], {})
            elif r["recipient_type"] == RECIPIENT_TYPE_USER:
                details = users_map.get(r["recipient_id"], {})
            result.append({**r, **details})

        return result


class CommunicationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.template_service = MessageTemplateService(session)
        self.recipient_resolver = RecipientResolver(session)

    async def send_message(
        self,
        data: Any,
        user: User,
        request: Any = None,
        tenant: Any = None,
    ) -> CommunicationMessage:
        """Create and deliver a message.

        ``tenant`` (the router's ``require_tenant_context``) is forwarded
        into the context loader so a context entity from another campus
        is rejected before its variables reach the message body.
        """
        if data.message_type not in MESSAGE_TYPES:
            raise ValidationError(f"Invalid message type: {data.message_type}")

        channels = [c for c in data.channels if c in ALL_CHANNELS]
        if not channels:
            channels = [CHANNEL_IN_APP]

        # P15 — context-aware send: load the linked entity's variables and
        # validate any parent recipients against it (a parent recipient must
        # be a guardian of the context student).
        context_vars: dict[str, Any] = {}
        if data.context_type and data.context_id:
            context_vars = await load_context_variables(
                self.session, data.context_type, data.context_id, tenant=tenant
            )
            if data.context_type == "student" and data.recipients:
                await self._validate_parent_recipients(data.context_id, data.recipients)

        recipients = await self.recipient_resolver.resolve(
            recipients=[r.model_dump() for r in data.recipients] if data.recipients else None,
            class_ids=data.class_ids,
            section_ids=data.section_ids,
        )

        if data.recipient_groups:
            for group in data.recipient_groups:
                for rid in group.recipient_ids:
                    recipients.append({
                        "recipient_type": group.recipient_type,
                        "recipient_id": rid,
                    })

        if not recipients and data.message_type not in (MSG_TYPE_ANNOUNCEMENT, MSG_TYPE_STAFF):
            raise ValidationError("At least one recipient is required for this message type")

        thread_id = data.thread_id
        if not thread_id and data.message_type == MSG_TYPE_TARGETED:
            thread = MessageThread(
                subject=data.subject,
                message_type=data.message_type,
                campus_id=getattr(user, "campus_id", None),
            )
            self.session.add(thread)
            await self.session.flush()
            thread_id = thread.id

        is_scheduled = data.schedule_at is not None and data.schedule_at > datetime.datetime.now(
            datetime.timezone.utc
        )

        # P15 — resolve template variables against the linked context and
        # the caller's explicit overrides; render before storing so the
        # stored message is exactly what the recipient reads.
        effective_vars: dict[str, Any] = {}
        for scope in (context_vars, getattr(data, "variables", None) or {}):
            for key, value in scope.items():
                effective_vars[key] = value
        if data.template_id and effective_vars:
            rendered = await self.template_service.render(
                data.template_id, effective_vars
            )
            body = rendered["body"] or data.body
            subject = rendered["subject"] or data.subject
        else:
            body = data.body
            subject = data.subject

        msg = CommunicationMessage(
            template_id=data.template_id,
            thread_id=thread_id,
            subject=subject,
            body=body,
            message_type=data.message_type,
            priority=data.priority,
            channels=channels,
            status=STATUS_SCHEDULED if is_scheduled else STATUS_DRAFT,
            scheduled_for=data.schedule_at,
            campus_id=getattr(user, "campus_id", None),
            sender_id=user.id,
            context_type=data.context_type,
            context_id=data.context_id,
        )
        self.session.add(msg)
        await self.session.flush()

        for r in recipients:
            for ch in channels:
                recipient = MessageRecipient(
                    message_id=msg.id,
                    recipient_type=r["recipient_type"],
                    recipient_id=r["recipient_id"],
                    channel=ch,
                    status=RECIPIENT_STATUS_PENDING,
                )
                self.session.add(recipient)

        if is_scheduled:
            schedule = MessageSchedule(
                message_id=msg.id,
                scheduled_at=data.schedule_at,
                timezone=data.timezone or "UTC",
                recurrence=data.recurrence or RECURRENCE_NONE,
                recurrence_end=data.recurrence_end,
                status=SCHEDULE_STATUS_PENDING,
            )
            self.session.add(schedule)
        else:
            msg.status = STATUS_SENT
            msg.sent_at = datetime.datetime.now(datetime.timezone.utc)

        await self.session.commit()
        await self.session.refresh(msg, ["recipients", "schedule"])

        if not is_scheduled:
            await self._deliver(msg)

        await self._audit("message.send", msg, user, request)
        return msg

    async def _validate_parent_recipients(
        self, student_id: int, recipients: list[Any]
    ) -> None:
        """P15 — a ``parent`` recipient must be a linked guardian of the
        context student, otherwise the sender could message any guardian
        record without an operational justification."""
        from app.domains.communications.context import load_guardian_user_ids

        guardian_ids = set(await load_guardian_user_ids(self.session, student_id))
        for r in recipients:
            if getattr(r, "recipient_type", None) == "parent" or (
                isinstance(r, dict) and r.get("recipient_type") == "parent"
            ):
                rid = r.get("recipient_id") if isinstance(r, dict) else getattr(r, "recipient_id")
                if rid not in guardian_ids:
                    raise ValidationError(
                        f"Parent #{rid} is not a guardian of student #{student_id} "
                        "and cannot be messaged in this context"
                    )

    async def load_context(
        self, context_type: str, context_id: int, tenant: Any = None
    ) -> dict[str, Any]:
        """P15 — summary + template variables for the composer's context
        badge and variable preview. ``tenant`` is forwarded to the loader
        for the cross-campus IDOR guard."""
        return await load_context_summary(self.session, context_type, context_id, tenant=tenant)

    def _in_app_provider(self):
        """P15 — the ``in_app`` channel has no vendor to call; delivery is a
        Notification row for user recipients (reusing the notification
        domain — never a second notification system). Registering a provider
        keeps the ProviderFactory abstraction and fixes the pre-existing
        behaviour where every in-app message was marked ``failed``.
        """
        from app.domains.communications.providers import (
            BaseProvider,
            DeliveryResult,
            ProviderFactory,
        )
        from app.domains.notifications.service import NotificationService

        session = self.session

        class InAppProvider(BaseProvider):
            async def send(self, message: ProviderMessage) -> DeliveryResult:
                data = message.metadata or {}
                user_id = data.get("user_id")
                if user_id is None:
                    return DeliveryResult(
                        success=False, provider="in_app",
                        error_message="No user for in-app delivery",
                    )
                try:
                    await NotificationService(session).create_notification(
                        user_id=int(user_id),
                        type=data.get("type", "message"),
                        title=data.get("title", message.subject or "Message"),
                        message=message.body or "",
                        data={"message_id": data.get("message_id")},
                    )
                    return DeliveryResult(success=True, provider="in_app")
                except Exception as exc:  # pragma: no cover — diagnostic path
                    logger = __import__("logging").getLogger(__name__)
                    logger.warning("in_app delivery failed: %s", exc, exc_info=True)
                    return DeliveryResult(
                        success=False, provider="in_app",
                        error_message=f"Notification creation failed: {exc}",
                    )

            async def health(self) -> bool:
                return True

        # Always build a fresh provider: it closes over THIS session, and
        # the factory's channel-level cache could hand an older request's
        # (stale) session back to this one.
        return InAppProvider()

    async def _deliver(self, msg: CommunicationMessage) -> None:
        from app.domains.communications.providers import ProviderFactory
        from app.domains.communications.providers import ProviderMessage

        in_app = self._in_app_provider()

        for recipient in msg.recipients:
            if recipient.status != RECIPIENT_STATUS_PENDING:
                continue

            try:
                # in-app messages are delivered through the notification
                # domain (the InAppProvider), not a vendor.
                if recipient.channel == CHANNEL_IN_APP:
                    provider = in_app
                else:
                    provider = ProviderFactory.get_provider(recipient.channel)
                target = await self._resolve_contact(recipient)

                if not target:
                    recipient.status = RECIPIENT_STATUS_FAILED
                    recipient.error_message = "No contact info available"
                    await self.session.flush()
                    continue

                pm = ProviderMessage(
                    to=target,
                    subject=msg.subject,
                    body=msg.body,
                    metadata={
                        # user and parent recipients map to user accounts
                        "user_id": recipient.recipient_id
                        if recipient.recipient_type in (RECIPIENT_TYPE_USER, RECIPIENT_TYPE_PARENT)
                        else None,
                        "message_id": msg.id,
                        "type": msg.message_type,
                        "title": msg.subject or "New message",
                    },
                )
                result = await provider.send(pm)

                if result.success:
                    recipient.status = RECIPIENT_STATUS_SENT
                    recipient.delivered_at = datetime.datetime.now(datetime.timezone.utc)
                else:
                    recipient.status = RECIPIENT_STATUS_FAILED
                    recipient.error_message = result.error_message

            except Exception as e:
                recipient.status = RECIPIENT_STATUS_FAILED
                recipient.error_message = str(e)

            await self.session.flush()

        total = len(msg.recipients)
        failed = sum(1 for r in msg.recipients if r.status == RECIPIENT_STATUS_FAILED)
        # A message with zero recipients (e.g. a broadcast-style announcement
        # with no explicit recipient rows) is vacuously delivered — never
        # treat ``0 == 0`` as "all failed".
        if total > 0 and failed == total:
            msg.status = STATUS_FAILED
        elif failed > 0:
            msg.status = STATUS_PARTIAL
        else:
            msg.status = STATUS_SENT

        await self.session.commit()

    async def _resolve_contact(self, recipient: MessageRecipient) -> Optional[str]:
        if recipient.recipient_type == RECIPIENT_TYPE_USER:
            user = await self.session.get(User, recipient.recipient_id)
            if user:
                if recipient.channel == "email":
                    return user.email
                return user.display_name
        elif recipient.recipient_type == RECIPIENT_TYPE_STUDENT:
            from app.domains.student.models import Student
            student = await self.session.get(Student, recipient.recipient_id)
            if student:
                if recipient.channel == "email":
                    return student.email or ""
                return f"{student.first_name} {student.last_name}"
        elif recipient.recipient_type == RECIPIENT_TYPE_PARENT:
            # A parent recipient references the guardian's *user* account.
            user = await self.session.get(User, recipient.recipient_id)
            if user:
                if recipient.channel == "email":
                    return user.email or ""
                return user.display_name
        return None

    async def dispatch_due_schedules(self) -> dict[str, int]:
        """Dispatch every pending message schedule whose time has come.

        Called by the periodic ``communications.scheduled`` job (worker
        process).  Selects ``MessageSchedule`` rows in ``pending`` whose
        ``scheduled_at`` is in the past, marks the message ``sent`` and
        delivers it, then marks the schedule ``completed`` (or ``failed``
        when every recipient failed).  A recurring schedule is advanced to
        its next occurrence instead of being completed.

        Returns a summary dict ``{"dispatched": n, "failed": n}``.  The
        method is safe to re-run: schedules that are already ``completed``
        or ``sending`` are never selected again, so a worker restart or
        duplicate job execution cannot double-deliver.
        """
        from sqlalchemy import select as _select
        from sqlalchemy.orm import selectinload as _selectinload

        from app.domains.communications.models import MessageSchedule
        from app.domains.communications.constants import (
            SCHEDULE_STATUS_PENDING,
            SCHEDULE_STATUS_COMPLETED,
            SCHEDULE_STATUS_FAILED,
            RECURRENCE_NONE,
        )

        now = datetime.datetime.now(datetime.timezone.utc)
        result = await self.session.execute(
            _select(MessageSchedule)
            .where(
                MessageSchedule.status == SCHEDULE_STATUS_PENDING,
                MessageSchedule.scheduled_at <= now,
            )
            .options(
                _selectinload(MessageSchedule.message).selectinload(
                    CommunicationMessage.recipients
                )
            )
        )
        schedules = list(result.scalars().all())

        dispatched = 0
        failed = 0
        for schedule in schedules:
            msg = schedule.message
            if msg is None:
                schedule.status = SCHEDULE_STATUS_FAILED
                await self.session.flush()
                failed += 1
                continue

            # Deliver (updates recipient + message status, commits).
            msg.status = STATUS_SENT
            msg.sent_at = datetime.datetime.now(datetime.timezone.utc)
            await self._deliver(msg)

            # Advance recurring schedules; complete one-shot schedules.
            next_at = None
            if schedule.recurrence != RECURRENCE_NONE:
                next_at = self._next_schedule_occurrence(schedule)
            if next_at is not None:
                schedule.scheduled_at = next_at
                schedule.last_sent_at = msg.sent_at
                schedule.status = SCHEDULE_STATUS_PENDING
            elif msg.status == STATUS_FAILED:
                schedule.status = SCHEDULE_STATUS_FAILED
                failed += 1
            else:
                schedule.status = SCHEDULE_STATUS_COMPLETED
                schedule.last_sent_at = msg.sent_at
                dispatched += 1
            await self.session.flush()

        await self.session.commit()
        return {"dispatched": dispatched, "failed": failed}

    @staticmethod
    def _next_schedule_occurrence(schedule: Any) -> Optional[datetime.datetime]:
        """Compute the next occurrence for a recurring schedule, or None."""
        from app.domains.communications.constants import (
            RECURRENCE_DAILY,
            RECURRENCE_WEEKLY,
            RECURRENCE_MONTHLY,
        )

        base = schedule.scheduled_at
        if schedule.recurrence == RECURRENCE_DAILY:
            nxt = base + datetime.timedelta(days=1)
        elif schedule.recurrence == RECURRENCE_WEEKLY:
            nxt = base + datetime.timedelta(weeks=1)
        elif schedule.recurrence == RECURRENCE_MONTHLY:
            year = base.year + (1 if base.month == 12 else 0)
            month = 1 if base.month == 12 else base.month + 1
            try:
                nxt = base.replace(year=year, month=month)
            except ValueError:  # e.g. Jan 31 -> Feb (no 31st)
                nxt = (base + datetime.timedelta(days=28)).replace(
                    hour=base.hour, minute=base.minute, second=base.second
                )
        else:
            return None

        if schedule.recurrence_end is not None and nxt > schedule.recurrence_end:
            return None
        return nxt

    async def list_messages(
        self,
        user: User,
        message_type: Optional[str] = None,
        status: Optional[str] = None,
        context_type: Optional[str] = None,
        context_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[CommunicationMessage], int]:
        """
        List the current user's sent messages, optionally filtered by
        message type / status and by the operational context they were
        composed from (P15).  ``context_type`` + ``context_id`` must be
        provided together — this powers "communication history for this
        student / case / fee due" on the sent-messages surface.
        """
        conditions = [CommunicationMessage.sender_id == user.id]

        if message_type:
            conditions.append(CommunicationMessage.message_type == message_type)
        if status:
            conditions.append(CommunicationMessage.status == status)
        if context_type and context_id:
            conditions.append(CommunicationMessage.context_type == context_type)
            conditions.append(CommunicationMessage.context_id == context_id)

        query = (
            select(CommunicationMessage)
            .where(*conditions)
            .options(
                selectinload(CommunicationMessage.recipients),
                selectinload(CommunicationMessage.attachments),
                selectinload(CommunicationMessage.schedule),
            )
            .offset(skip)
            .limit(limit)
            .order_by(CommunicationMessage.created_at.desc())
        )
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        count_query = select(func.count(CommunicationMessage.id)).where(*conditions)
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0
        return items, total

    async def get_message(self, msg_id: int, user: User) -> CommunicationMessage:
        result = await self.session.execute(
            select(CommunicationMessage)
            .where(CommunicationMessage.id == msg_id)
            .options(
                selectinload(CommunicationMessage.recipients),
                selectinload(CommunicationMessage.attachments),
                selectinload(CommunicationMessage.schedule),
            )
        )
        msg = result.scalar_one_or_none()
        if not msg:
            raise NotFoundError("Message not found")
        return msg

    async def update_message(self, msg_id: int, data: Any, user: User) -> CommunicationMessage:
        msg = await self.get_message(msg_id, user)
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(msg, key, value)
        await self.session.commit()
        await self.session.refresh(msg, ["recipients", "attachments", "schedule"])
        return msg

    async def delete_message(self, msg_id: int, user: User) -> None:
        msg = await self.get_message(msg_id, user)
        await self.session.delete(msg)
        await self.session.commit()

    async def get_stats(self, user: User) -> dict[str, Any]:
        conditions = [CommunicationMessage.sender_id == user.id]
        base = select(CommunicationMessage).where(*conditions)

        total_result = await self.session.execute(select(func.count()).select_from(base.subquery()))
        total_sent = total_result.scalar() or 0

        recipient_counts = await self.session.execute(
            select(
                MessageRecipient.status,
                func.count(MessageRecipient.id),
            )
            .where(
                MessageRecipient.message_id.in_(
                    select(CommunicationMessage.id).where(*conditions)
                )
            )
            .group_by(MessageRecipient.status)
        )

        by_status = dict(recipient_counts.all())

        type_counts = await self.session.execute(
            select(CommunicationMessage.message_type, func.count(CommunicationMessage.id))
            .where(*conditions)
            .group_by(CommunicationMessage.message_type)
        )

        return {
            "total_sent": total_sent,
            "total_delivered": by_status.get(RECIPIENT_STATUS_DELIVERED, 0) + by_status.get(RECIPIENT_STATUS_READ, 0),
            "total_failed": by_status.get(RECIPIENT_STATUS_FAILED, 0),
            "total_read": by_status.get(RECIPIENT_STATUS_READ, 0),
            "by_type": dict(type_counts.all()),
            "by_channel": {},
        }

    async def retry_delivery(
        self, msg_id: int, user: User,
        recipient_ids: Optional[list[int]] = None,
    ) -> CommunicationMessage:
        msg = await self.get_message(msg_id, user)

        conditions = [MessageRecipient.message_id == msg_id, MessageRecipient.status == RECIPIENT_STATUS_FAILED]
        if recipient_ids:
            conditions.append(MessageRecipient.id.in_(recipient_ids))

        result = await self.session.execute(
            select(MessageRecipient).where(*conditions)
        )
        failed_recipients = list(result.scalars().all())

        for r in failed_recipients:
            r.status = RECIPIENT_STATUS_PENDING
            r.error_message = None

        await self.session.commit()
        await self._deliver(msg)
        return msg

    async def get_preferences(self, user_id: int) -> Sequence[CommunicationPreference]:
        result = await self.session.execute(
            select(CommunicationPreference).where(CommunicationPreference.user_id == user_id)
        )
        return list(result.scalars().all())

    async def update_preference(self, user_id: int, channel: str, enabled: bool) -> CommunicationPreference:
        result = await self.session.execute(
            select(CommunicationPreference).where(
                CommunicationPreference.user_id == user_id,
                CommunicationPreference.channel == channel,
            )
        )
        pref = result.scalar_one_or_none()
        if pref:
            pref.enabled = enabled
        else:
            pref = CommunicationPreference(user_id=user_id, channel=channel, enabled=enabled)
            self.session.add(pref)
        await self.session.commit()
        await self.session.refresh(pref)
        return pref

    async def get_inbox(self, user: User, skip: int = 0, limit: int = 20) -> tuple[Sequence[MessageRecipient], int]:
        conditions = [
            MessageRecipient.recipient_type == RECIPIENT_TYPE_USER,
            MessageRecipient.recipient_id == user.id,
        ]
        query = (
            select(MessageRecipient)
            .where(*conditions)
            .options(selectinload(MessageRecipient.message))
            .offset(skip)
            .limit(limit)
            .order_by(MessageRecipient.created_at.desc())
        )
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        count_result = await self.session.execute(
            select(func.count(MessageRecipient.id)).where(*conditions)
        )
        total = count_result.scalar() or 0
        return items, total

    async def mark_as_read(self, recipient_id: int, user: User) -> MessageRecipient:
        result = await self.session.execute(
            select(MessageRecipient).where(
                MessageRecipient.id == recipient_id,
                MessageRecipient.recipient_type == RECIPIENT_TYPE_USER,
                MessageRecipient.recipient_id == user.id,
            )
        )
        recipient = result.scalar_one_or_none()
        if not recipient:
            raise NotFoundError("Recipient record not found")
        recipient.status = RECIPIENT_STATUS_READ
        recipient.read_at = datetime.datetime.now(datetime.timezone.utc)
        await self.session.commit()
        await self.session.refresh(recipient)
        return recipient

    async def _audit(self, action: str, msg: CommunicationMessage, user: User, request: Any = None) -> None:
        from app.domains.audit.service import AuditService
        from app.domains.audit.utils import get_request_metadata

        metadata = get_request_metadata(request) if request else {}
        details = {
            "message_id": msg.id,
            "message_type": msg.message_type,
            "status": msg.status,
            "channel_count": len(msg.channels),
            "recipient_count": len(msg.recipients) if msg.recipients else 0,
            "context_type": msg.context_type,
            "context_id": msg.context_id,
            "template_id": msg.template_id,
        }
        await AuditService(self.session).record(
            action=action,
            resource_type="communication_message",
            resource_id=str(msg.id),
            details=details,
            user_id=user.id,
            username=getattr(user, "username", None),
            **metadata,
        )
