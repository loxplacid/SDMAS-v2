from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class MessageTemplateCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    subject: Optional[str] = Field(None, max_length=500)
    body: str = Field(..., min_length=1)
    message_type: str = Field(default="announcement")
    channels: list[str] = Field(default=["in_app"])
    variables: Optional[list[dict[str, Any]]] = None


class MessageTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    subject: Optional[str] = Field(None, max_length=500)
    body: Optional[str] = None
    message_type: Optional[str] = None
    channels: Optional[list[str]] = None
    variables: Optional[list[dict[str, Any]]] = None
    is_active: Optional[bool] = None


class MessageTemplateResponse(BaseModel):
    id: int
    code: str
    name: str
    subject: Optional[str]
    body: str
    message_type: str
    channels: list[str]
    variables: Optional[list[dict[str, Any]]]
    is_active: bool
    campus_id: Optional[int]
    created_by: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class RecipientTarget(BaseModel):
    recipient_type: str = Field(..., pattern="^(user|student|teacher|parent)$")
    recipient_id: int = Field(..., ge=1)


class BulkRecipientTarget(BaseModel):
    recipient_type: str = Field(..., pattern="^(user|student|teacher|parent)$")
    recipient_ids: list[int] = Field(..., min_length=1)


class ClassTarget(BaseModel):
    class_id: int = Field(..., ge=1)


class SectionTarget(BaseModel):
    section_id: int = Field(..., ge=1)


class MessageSend(BaseModel):
    template_id: Optional[int] = None
    thread_id: Optional[int] = None
    subject: Optional[str] = Field(None, max_length=500)
    body: str = Field(..., min_length=1)
    message_type: str = Field(default="targeted")
    priority: str = Field(default="normal")
    channels: list[str] = Field(default=["in_app"])
    recipients: Optional[list[RecipientTarget]] = None
    recipient_groups: Optional[list[BulkRecipientTarget]] = None
    class_ids: Optional[list[int]] = None
    section_ids: Optional[list[int]] = None
    schedule_at: Optional[datetime.datetime] = None
    timezone: str = Field(default="UTC")
    recurrence: str = Field(default="none")
    recurrence_end: Optional[datetime.datetime] = None
    # P15 — the operational context the message is composed from. When set,
    # template variables are resolved against the linked entity and the
    # message stays associated with it.
    context_type: Optional[str] = None
    context_id: Optional[int] = None
    variables: Optional[dict[str, Any]] = None


class ContextPreviewRequest(BaseModel):
    """Render a template against a live operational context (P15).

    ``variables`` may override or extend the entity-derived values — an
    operator can tweak a reminder amount without editing the template.
    """

    template_id: int
    context_type: str
    context_id: int
    variables: dict[str, Any] = {}


class MessageUpdate(BaseModel):
    subject: Optional[str] = Field(None, max_length=500)
    body: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None


class MessageRecipientResponse(BaseModel):
    id: int
    message_id: int
    recipient_type: str
    recipient_id: int
    channel: str
    status: str
    delivered_at: Optional[datetime.datetime]
    read_at: Optional[datetime.datetime]
    error_message: Optional[str]
    created_at: datetime.datetime


class MessageAttachmentResponse(BaseModel):
    id: int
    message_id: int
    filename: str
    mime_type: str
    file_size: int
    created_at: datetime.datetime


class MessageScheduleResponse(BaseModel):
    id: int
    message_id: int
    scheduled_at: datetime.datetime
    status: str
    timezone: str
    recurrence: str
    recurrence_end: Optional[datetime.datetime]
    last_sent_at: Optional[datetime.datetime]
    created_at: datetime.datetime


class MessageResponse(BaseModel):
    id: int
    template_id: Optional[int]
    thread_id: Optional[int]
    subject: Optional[str]
    body: str
    message_type: str
    priority: str
    channels: list[str]
    status: str
    scheduled_for: Optional[datetime.datetime]
    sent_at: Optional[datetime.datetime]
    campus_id: Optional[int]
    sender_id: int
    # P15 — context the message was composed from.
    context_type: Optional[str]
    context_id: Optional[int]
    created_at: datetime.datetime
    updated_at: datetime.datetime
    recipients: list[MessageRecipientResponse] = []
    attachments: list[MessageAttachmentResponse] = []
    schedule: Optional[MessageScheduleResponse] = None
    recipient_count: int = 0
    delivered_count: int = 0
    failed_count: int = 0
    read_count: int = 0


class MessagePage(BaseModel):
    items: list[MessageResponse]
    total: int
    page: int
    size: int
    pages: int


class MessageStats(BaseModel):
    total_sent: int = 0
    total_delivered: int = 0
    total_failed: int = 0
    total_read: int = 0
    by_type: dict[str, int] = {}
    by_channel: dict[str, int] = {}


class CommunicationPreferenceUpdate(BaseModel):
    channel: str = Field(..., pattern="^(email|sms|push|whatsapp|in_app)$")
    enabled: bool


class CommunicationPreferenceResponse(BaseModel):
    id: int
    user_id: int
    channel: str
    enabled: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


class DeliveryRetryRequest(BaseModel):
    recipient_ids: Optional[list[int]] = None
    channel: Optional[str] = None


class TemplateRenderRequest(BaseModel):
    template_id: int
    variables: dict[str, Any] = {}


class RecipientResolveRequest(BaseModel):
    recipient_type: str = Field(..., pattern="^(user|student|teacher|parent)$")
    recipient_ids: Optional[list[int]] = None
    class_ids: Optional[list[int]] = None
    section_ids: Optional[list[int]] = None


class RecipientResolveResponse(BaseModel):
    recipients: list[dict[str, Any]]
    total: int


class ContextInfoResponse(BaseModel):
    """Summary of an operational context plus the template variables it
    makes available (P15) — drives the composer's context badge and the
    variable preview panel."""

    context_type: str
    context_id: int
    label: str
    detail: str
    variables: dict[str, Any]
    guardian_ids: list[int] = []


class ContextVariableListResponse(BaseModel):
    context_type: str
    context_id: int
    variables: dict[str, Any]


class InboxMessageInfo(BaseModel):
    id: int
    subject: Optional[str] = None
    body: str
    message_type: str
    sender_id: int
    created_at: str


class InboxItemResponse(BaseModel):
    id: int
    message_id: int
    recipient_type: str
    recipient_id: int
    channel: str
    status: str
    delivered_at: Optional[datetime.datetime] = None
    read_at: Optional[datetime.datetime] = None
    error_message: Optional[str] = None
    created_at: datetime.datetime
    message: Optional[InboxMessageInfo] = None
