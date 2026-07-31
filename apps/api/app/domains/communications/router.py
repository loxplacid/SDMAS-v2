from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PaginationParams
from app.domains.auth.dependencies import get_current_user, require_role
from app.domains.auth.models import User
from app.domains.communications.constants import MESSAGE_TYPES, ALL_CHANNELS
from app.domains.communications.schemas import (
    CommunicationPreferenceResponse,
    CommunicationPreferenceUpdate,
    DeliveryRetryRequest,
    InboxItemResponse,
    InboxMessageInfo,
    MessagePage,
    MessageRecipientResponse,
    MessageResponse,
    MessageScheduleResponse,
    MessageSend,
    MessageStats,
    MessageTemplateCreate,
    MessageTemplateResponse,
    MessageTemplateUpdate,
    MessageUpdate,
    RecipientResolveRequest,
    RecipientResolveResponse,
    TemplateRenderRequest,
)
from app.domains.communications.service import (
    CommunicationService,
    MessageTemplateService,
    RecipientResolver,
)
from app.infrastructure.database import get_session

router = APIRouter(prefix="/api/communications", tags=["communications"])


async def get_template_svc(session: AsyncSession = Depends(get_session)) -> MessageTemplateService:
    return MessageTemplateService(session)


async def get_comm_svc(session: AsyncSession = Depends(get_session)) -> CommunicationService:
    return CommunicationService(session)


async def get_resolver(session: AsyncSession = Depends(get_session)) -> RecipientResolver:
    return RecipientResolver(session)


# ── Templates ──


@router.get("/templates", response_model=list[MessageTemplateResponse])
async def list_templates(
    svc: MessageTemplateService = Depends(get_template_svc),
    _user: User = Depends(require_role("admin", "staff", "teacher", "principal")),
) -> list[MessageTemplateResponse]:
    items, _ = await svc.list()
    return [MessageTemplateResponse.model_validate(t) for t in items]


@router.post("/templates", response_model=MessageTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: MessageTemplateCreate,
    current_user: User = Depends(require_role("admin", "staff")),
    svc: MessageTemplateService = Depends(get_template_svc),
) -> MessageTemplateResponse:
    tpl = await svc.create(data, current_user)
    return MessageTemplateResponse.model_validate(tpl)


@router.get("/templates/{template_id}", response_model=MessageTemplateResponse)
async def get_template(
    template_id: int,
    _user: User = Depends(require_role("admin", "staff", "teacher", "principal")),
    svc: MessageTemplateService = Depends(get_template_svc),
) -> MessageTemplateResponse:
    tpl = await svc.get(template_id)
    return MessageTemplateResponse.model_validate(tpl)


@router.patch("/templates/{template_id}", response_model=MessageTemplateResponse)
async def update_template(
    template_id: int,
    data: MessageTemplateUpdate,
    _user: User = Depends(require_role("admin", "staff")),
    svc: MessageTemplateService = Depends(get_template_svc),
) -> MessageTemplateResponse:
    tpl = await svc.update(template_id, data)
    return MessageTemplateResponse.model_validate(tpl)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    _user: User = Depends(require_role("admin")),
    svc: MessageTemplateService = Depends(get_template_svc),
) -> None:
    await svc.delete(template_id)


@router.post("/templates/render", response_model=dict)
async def render_template(
    data: TemplateRenderRequest,
    _user: User = Depends(require_role("admin", "staff", "teacher", "principal")),
    svc: MessageTemplateService = Depends(get_template_svc),
) -> dict:
    return await svc.render(data.template_id, data.variables)


# ── Recipient Resolution ──


@router.post("/resolve-recipients", response_model=RecipientResolveResponse)
async def resolve_recipients(
    data: RecipientResolveRequest,
    _user: User = Depends(require_role("admin", "staff", "teacher")),
    svc: RecipientResolver = Depends(get_resolver),
) -> RecipientResolveResponse:
    recipients = await svc.resolve_with_details(
        recipients=[{"recipient_type": data.recipient_type, "recipient_id": rid}
                     for rid in data.recipient_ids] if data.recipient_ids else None,
        class_ids=data.class_ids,
        section_ids=data.section_ids,
    )
    return RecipientResolveResponse(recipients=recipients, total=len(recipients))


# ── Messages ──


@router.post("/send", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    data: MessageSend,
    request: Request = None,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "principal")),
    svc: CommunicationService = Depends(get_comm_svc),
) -> MessageResponse:
    msg = await svc.send_message(data, current_user, request=request)
    return _build_message_response(msg)


@router.get("/messages", response_model=MessagePage)
async def list_messages(
    pagination: PaginationParams = Depends(),
    message_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(require_role("admin", "staff", "teacher", "principal")),
    svc: CommunicationService = Depends(get_comm_svc),
) -> MessagePage:
    items, total = await svc.list_messages(
        user=current_user,
        message_type=message_type,
        status=status,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    result = [_build_message_response(m) for m in items]
    return Page.create(items=result, total=total, page=pagination.page, size=pagination.size)


@router.get("/messages/{msg_id}", response_model=MessageResponse)
async def get_message(
    msg_id: int,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "principal")),
    svc: CommunicationService = Depends(get_comm_svc),
) -> MessageResponse:
    msg = await svc.get_message(msg_id, current_user)
    return _build_message_response(msg)


@router.patch("/messages/{msg_id}", response_model=MessageResponse)
async def update_message(
    msg_id: int,
    data: MessageUpdate,
    current_user: User = Depends(require_role("admin", "staff")),
    svc: CommunicationService = Depends(get_comm_svc),
) -> MessageResponse:
    msg = await svc.update_message(msg_id, data, current_user)
    return _build_message_response(msg)


@router.delete("/messages/{msg_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    msg_id: int,
    current_user: User = Depends(require_role("admin", "staff")),
    svc: CommunicationService = Depends(get_comm_svc),
) -> None:
    await svc.delete_message(msg_id, current_user)


# ── Delivery ──


@router.post("/messages/{msg_id}/retry", response_model=MessageResponse)
async def retry_delivery(
    msg_id: int,
    data: Optional[DeliveryRetryRequest] = None,
    current_user: User = Depends(require_role("admin", "staff")),
    svc: CommunicationService = Depends(get_comm_svc),
) -> MessageResponse:
    msg = await svc.retry_delivery(
        msg_id, current_user,
        recipient_ids=data.recipient_ids if data else None,
    )
    return _build_message_response(msg)


@router.post("/messages/{msg_id}/send-now", response_model=MessageResponse)
async def send_scheduled_now(
    msg_id: int,
    request: Request = None,
    current_user: User = Depends(require_role("admin", "staff")),
    svc: CommunicationService = Depends(get_comm_svc),
) -> MessageResponse:
    msg = await svc.get_message(msg_id, current_user)
    if msg.schedule:
        from app.domains.communications.constants import SCHEDULE_STATUS_COMPLETED
        msg.schedule.status = SCHEDULE_STATUS_COMPLETED
    from app.domains.communications.constants import STATUS_SENT
    msg.status = STATUS_SENT
    msg.scheduled_for = None
    await svc.session.commit()
    await svc._deliver(msg)
    return _build_message_response(msg)


# ── Inbox ──


@router.get("/inbox", response_model=Page[InboxItemResponse])
async def get_inbox(
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    svc: CommunicationService = Depends(get_comm_svc),
) -> Page[InboxItemResponse]:
    items, total = await svc.get_inbox(current_user, skip=pagination.offset, limit=pagination.limit)
    result = []
    for r in items:
        data = MessageRecipientResponse.model_validate(r)
        msg = None
        if r.message:
            msg = InboxMessageInfo(
                id=r.message.id,
                subject=r.message.subject,
                body=r.message.body,
                message_type=r.message.message_type,
                sender_id=r.message.sender_id,
                created_at=r.message.created_at.isoformat(),
            )
        result.append(InboxItemResponse(
            **data.model_dump(),
            message=msg,
        ))
    return Page.create(items=result, total=total, page=pagination.page, size=pagination.size)


@router.post("/inbox/{recipient_id}/read", response_model=MessageRecipientResponse)
async def mark_as_read(
    recipient_id: int,
    current_user: User = Depends(get_current_user),
    svc: CommunicationService = Depends(get_comm_svc),
) -> MessageRecipientResponse:
    recipient = await svc.mark_as_read(recipient_id, current_user)
    return MessageRecipientResponse.model_validate(recipient)


# ── Preferences ──


@router.get("/preferences", response_model=list[CommunicationPreferenceResponse])
async def get_preferences(
    current_user: User = Depends(get_current_user),
    svc: CommunicationService = Depends(get_comm_svc),
) -> list[CommunicationPreferenceResponse]:
    prefs = await svc.get_preferences(current_user.id)
    return [CommunicationPreferenceResponse.model_validate(p) for p in prefs]


@router.patch("/preferences/{channel}", response_model=CommunicationPreferenceResponse)
async def update_preference(
    channel: str,
    data: CommunicationPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    svc: CommunicationService = Depends(get_comm_svc),
) -> CommunicationPreferenceResponse:
    pref = await svc.update_preference(current_user.id, channel, data.enabled)
    return CommunicationPreferenceResponse.model_validate(pref)


# ── Stats ──


@router.get("/stats", response_model=MessageStats)
async def get_stats(
    current_user: User = Depends(require_role("admin", "staff")),
    svc: CommunicationService = Depends(get_comm_svc),
) -> MessageStats:
    stats = await svc.get_stats(current_user)
    return MessageStats(**stats)


# ── Metadata ──


@router.get("/meta/message-types", response_model=list[str])
async def get_message_types() -> list[str]:
    return MESSAGE_TYPES


@router.get("/meta/channels", response_model=list[str])
async def get_channels() -> list[str]:
    return ALL_CHANNELS


# ── Recurring Schedules (admin) ──


@router.get("/schedules/pending", response_model=list[MessageScheduleResponse])
async def get_pending_schedules(
    _user: User = Depends(require_role("admin")),
    svc: CommunicationService = Depends(get_comm_svc),
) -> list[MessageScheduleResponse]:
    from sqlalchemy import select
    from app.domains.communications.models import MessageSchedule
    from app.domains.communications.constants import SCHEDULE_STATUS_PENDING

    now = datetime.datetime.now(datetime.timezone.utc)
    result = await svc.session.execute(
        select(MessageSchedule)
        .where(
            MessageSchedule.status == SCHEDULE_STATUS_PENDING,
            MessageSchedule.scheduled_at <= now,
        )
        .options(selectinload(MessageSchedule.message))
    )
    schedules = list(result.scalars().all())
    return [MessageScheduleResponse.model_validate(s) for s in schedules]


import datetime
from sqlalchemy.orm import selectinload

from app.domains.communications.models import MessageRecipient


def _build_message_response(msg: CommunicationMessage) -> MessageResponse:
    resp = MessageResponse.model_validate(msg)
    if msg.recipients:
        resp.recipients = [MessageRecipientResponse.model_validate(r) for r in msg.recipients]
        resp.recipient_count = len(msg.recipients)
        resp.delivered_count = sum(1 for r in msg.recipients if r.status in ("sent", "delivered", "read"))
        resp.failed_count = sum(1 for r in msg.recipients if r.status in ("failed", "bounced"))
        resp.read_count = sum(1 for r in msg.recipients if r.status == "read")
    if msg.schedule:
        resp.schedule = MessageScheduleResponse.model_validate(msg.schedule)
    return resp
