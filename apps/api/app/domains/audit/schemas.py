from __future__ import annotations

import datetime
from typing import Any, Optional

import json

from pydantic import BaseModel, ConfigDict, field_validator


# ---------------------------------------------------------------------------
# AuditLog schemas
# ---------------------------------------------------------------------------


class AuditLogResponse(BaseModel):
    """Schema returned when querying audit logs."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None = None
    username: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    details: Any = None
    ip_address: str | None = None
    user_agent: str | None = None
    campus_id: int | None = None
    created_at: datetime.datetime

    @field_validator("details", mode="before")
    @classmethod
    def parse_details_json(cls, v: Any) -> Any:
        """Automatically parse the JSON string stored in the DB
        into a Python object so the API returns proper JSON."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return v
        return v


# ---------------------------------------------------------------------------
# Filter schemas
# ---------------------------------------------------------------------------


class AuditLogFilter(BaseModel):
    """Filters accepted by the audit log query endpoint."""

    user_id: Optional[int] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    campus_id: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
