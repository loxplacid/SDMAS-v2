from __future__ import annotations

import datetime
import json
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# AuditLog schemas
# ---------------------------------------------------------------------------


class AuditLogResponse(BaseModel):
    """Schema returned when querying audit logs."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: str | None = None
    user_id: int | None = None
    username: str | None = None
    actor_type: str | None = None
    actor_id: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    details: Any = None
    before_state: Any = None
    after_state: Any = None
    result: str | None = None
    failure_reason: str | None = None
    # ORM attribute is ``metadata_json`` (``metadata`` is reserved in
    # SQLAlchemy declarative), mapped back to the API field ``metadata``.
    metadata: Any = Field(default=None, validation_alias="metadata_json")
    ip_address: str | None = None
    user_agent: str | None = None
    campus_id: int | None = None
    tenant_id: int | None = None
    request_id: str | None = None
    correlation_id: str | None = None
    created_at: datetime.datetime

    @field_validator("details", "before_state", "after_state", "metadata", mode="before")
    @classmethod
    def parse_json_fields(cls, v: Any) -> Any:
        """Automatically parse JSON strings stored in the DB into Python
        objects so the API returns proper JSON."""
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
    actor_type: Optional[str] = None
    actor_id: Optional[str] = None
    result: Optional[str] = None
