from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.report_builder.base import BaseReportBuilder
from app.domains.report_builder.models import ReportDefinition


class ReportRegistry:
    _builders: dict[str, type[BaseReportBuilder]] = {}

    @classmethod
    def register(cls, builder_cls: type[BaseReportBuilder]) -> type[BaseReportBuilder]:
        meta = builder_cls.meta()
        cls._builders[meta.code] = builder_cls
        return builder_cls

    @classmethod
    def get(cls, code: str) -> Optional[type[BaseReportBuilder]]:
        return cls._builders.get(code)

    @classmethod
    def get_all(cls) -> list[type[BaseReportBuilder]]:
        return list(cls._builders.values())

    @classmethod
    def list_meta(cls) -> list[dict[str, Any]]:
        return [
            {
                "code": b.meta().code,
                "name": b.meta().name,
                "description": b.meta().description,
                "category": b.meta().category,
                "allowed_roles": b.meta().allowed_roles,
                "filters": [f.__dict__ for f in b.meta().filters],
                "columns": [c.__dict__ for c in b.meta().columns],
                "default_params": b.meta().default_params,
            }
            for b in cls._builders.values()
        ]

    @classmethod
    async def ensure_definitions(cls, session: AsyncSession) -> None:
        for builder_cls in cls._builders.values():
            meta = builder_cls.meta()
            existing = await session.execute(
                select(ReportDefinition).where(ReportDefinition.code == meta.code)
            )
            existing_def = existing.scalar_one_or_none()
            if not existing_def:
                session.add(
                    ReportDefinition(
                        code=meta.code,
                        name=meta.name,
                        description=meta.description,
                        category=meta.category,
                        allowed_roles=meta.allowed_roles,
                        config={"filters": [f.__dict__ for f in meta.filters], "columns": [c.__dict__ for c in meta.columns]},
                    )
                )
        await session.commit()
