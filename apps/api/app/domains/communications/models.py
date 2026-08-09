from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class MessageTemplate(Base):
    __tablename__ = "message_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(20), nullable=False, default="announcement")
    channels: Mapped[list] = mapped_column(JSON, nullable=False, default=["in_app"])
    variables: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    campus_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list[CommunicationMessage]] = relationship(
        "CommunicationMessage", back_populates="template", lazy="dynamic"
    )


class CommunicationMessage(Base):
    __tablename__ = "communication_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("message_templates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    thread_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("message_threads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(20), nullable=False, default="announcement", index=True)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="normal")
    channels: Mapped[list] = mapped_column(JSON, nullable=False, default=["in_app"])
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    scheduled_for: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # P15 — the operational context this message was composed from
    # (student / case / fee_due / admission). Polymorphic by design: no FK,
    # nullable, indexed so "messages for this entity" stays cheap.
    context_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    context_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    campus_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
    )
    sender_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    template: Mapped[Optional[MessageTemplate]] = relationship("MessageTemplate", back_populates="messages")
    thread: Mapped[Optional[MessageThread]] = relationship(
        "MessageThread", back_populates="messages", foreign_keys=[thread_id]
    )
    recipients: Mapped[list[MessageRecipient]] = relationship(
        "MessageRecipient", back_populates="message", cascade="all, delete-orphan"
    )
    attachments: Mapped[list[MessageAttachment]] = relationship(
        "MessageAttachment", back_populates="message", cascade="all, delete-orphan"
    )
    schedule: Mapped[Optional[MessageSchedule]] = relationship(
        "MessageSchedule", back_populates="message", uselist=False, cascade="all, delete-orphan"
    )


class MessageRecipient(Base):
    __tablename__ = "message_recipients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("communication_messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipient_type: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    recipient_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="in_app")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    delivered_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    message: Mapped[CommunicationMessage] = relationship("CommunicationMessage", back_populates="recipients")


class MessageAttachment(Base):
    __tablename__ = "message_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("communication_messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    message: Mapped[CommunicationMessage] = relationship("CommunicationMessage", back_populates="attachments")


class MessageSchedule(Base):
    __tablename__ = "message_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("communication_messages.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    scheduled_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="UTC")
    recurrence: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    recurrence_end: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sent_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    message: Mapped[CommunicationMessage] = relationship("CommunicationMessage", back_populates="schedule")


class MessageThread(Base):
    __tablename__ = "message_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    message_type: Mapped[str] = mapped_column(String(20), nullable=False, default="targeted")
    campus_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list[CommunicationMessage]] = relationship(
        "CommunicationMessage", back_populates="thread", foreign_keys="[CommunicationMessage.thread_id]"
    )


class CommunicationPreference(Base):
    __tablename__ = "communication_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="in_app")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
