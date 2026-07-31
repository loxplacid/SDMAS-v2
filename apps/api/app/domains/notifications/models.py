from __future__ import annotations

import datetime
from datetime import timezone
from typing import Optional

import json

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class JSONText(TypeDecorator):
    """Cross-database JSON column type.

    Stores JSON as TEXT on SQLite and as JSONB on PostgreSQL.
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: object | None, dialect) -> str | None:
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value: str | None, dialect) -> object | None:
        if value is not None:
            return json.loads(value)
        return None


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="system"
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[Optional[dict]] = mapped_column(
        type_=JSONText,
        nullable=True,
    )
    read_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<Notification id={self.id} "
            f"user_id={self.user_id} "
            f"type={self.type} "
            f"title={self.title}>"
        )

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


class DeviceToken(Base):
    """Stores Expo push tokens for delivering push notifications."""

    __tablename__ = "device_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    token: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    platform: Mapped[str] = mapped_column(
        String(20), nullable=False, default="android"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<DeviceToken id={self.id} "
            f"user_id={self.user_id} "
            f"platform={self.platform}>"
        )
