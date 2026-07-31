from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ReportFilter:
    key: str
    label: str
    type: str
    required: bool = False
    options: Optional[list[dict[str, str]]] = None
    placeholder: Optional[str] = None


@dataclass
class ReportColumn:
    key: str
    header: str
    type: str = "string"
    format: Optional[str] = None


@dataclass
class ReportMeta:
    code: str
    name: str
    description: str
    category: str
    allowed_roles: list[str]
    filters: list[ReportFilter] = field(default_factory=list)
    columns: list[ReportColumn] = field(default_factory=list)
    default_params: dict[str, Any] = field(default_factory=dict)


class BaseReportBuilder(ABC):
    @classmethod
    @abstractmethod
    def meta(cls) -> ReportMeta:
        pass

    @classmethod
    def validate_params(cls, params: dict[str, Any]) -> dict[str, str]:
        errors: dict[str, str] = {}
        for f in cls.meta().filters:
            if f.required and not params.get(f.key):
                errors[f.key] = f"{f.label} is required"
        return errors

    @abstractmethod
    async def fetch_data(
        self, params: dict[str, Any], user_id: int, campus_id: Optional[int], session: Any
    ) -> Any:
        pass

    @abstractmethod
    def build_rows(self, data: Any) -> list[dict[str, Any]]:
        pass

    def build_summary(self, data: Any) -> dict[str, Any]:
        return {}

    def total_rows_hint(self, params: dict[str, Any]) -> Optional[int]:
        return None
