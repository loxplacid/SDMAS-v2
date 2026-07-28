from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


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



