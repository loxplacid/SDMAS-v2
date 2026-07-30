from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    type: str
    title: str
    message: str
    data: Optional[dict] = None
    read_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


class UnreadCountResponse(BaseModel):
    count: int


# ---------------------------------------------------------------------------
# Push / Device Token Schemas
# ---------------------------------------------------------------------------


class DeviceTokenRegisterRequest(BaseModel):
    """Request body for registering a push notification device token."""

    token: str
    platform: str

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = {"android", "ios", "web"}
        if v.lower() not in allowed:
            raise ValueError(f"Platform must be one of: {', '.join(sorted(allowed))}")
        return v.lower()

    @field_validator("token")
    @classmethod
    def token_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Token cannot be empty")
        if not stripped.startswith("ExponentPushToken"):
            raise ValueError("Token must be a valid Expo push token")
        return stripped


class DeviceTokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    token: str
    platform: str
    created_at: datetime.datetime


class PushSendRequest(BaseModel):
    """Request body for sending a push notification."""

    user_id: int
    title: str
    body: str
    data: Optional[dict] = None


class PushTicketResponse(BaseModel):
    """Response from the Expo Push API for a single push message."""

    status: str
    id: Optional[str] = None
    message: Optional[str] = None
