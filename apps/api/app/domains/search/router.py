from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.dependencies import get_current_user
from app.domains.auth.models import User
from app.domains.search.schemas import (
    FrequentSearchResponse,
    GlobalSearchQuery,
    GlobalSearchResponse,
    IndexSyncResponse,
    SearchHistoryPage,
    SearchHistoryResponse,
)
from app.domains.search.service import SearchService
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import get_current_tenant
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/search", tags=["Search"])


@router.get("/index/sync", response_model=IndexSyncResponse)
async def index_sync(
    entity_type: str = Query(..., description="Entity type to sync"),
    page: int = Query(default=0, ge=0, le=10000),
    size: int = Query(default=200, ge=1, le=500),
    since: Optional[str] = Query(
        default=None,
        description="Only rows changed after this ISO timestamp (incremental)",
    ),
    current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
) -> IndexSyncResponse:
    """Feed the browser's local FTS5 index.

    Permission-scoped: only entity types the caller's role may view are
    returned (``service.sync_index`` enforces this). Tenant-scoped: rows
    are filtered to the active campus.
    """
    service = SearchService(session, current_user, tenant)
    return await service.sync_index(entity_type, page, size, since)


@router.post("")
async def global_search(
    params: GlobalSearchQuery,
    current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
) -> GlobalSearchResponse:
    service = SearchService(session, current_user, tenant)
    return await service.global_search(params)


@router.get("/recent", response_model=list[SearchHistoryResponse])
async def recent_searches(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
) -> list[SearchHistoryResponse]:
    service = SearchService(session, current_user, tenant)
    history = await service.get_recent_searches(limit)
    return [SearchHistoryResponse.model_validate(h) for h in history]


@router.get("/frequent", response_model=list[FrequentSearchResponse])
async def frequent_searches(
    limit: int = Query(default=5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
) -> list[FrequentSearchResponse]:
    service = SearchService(session, current_user, tenant)
    results = await service.get_frequent_searches(limit)
    return [FrequentSearchResponse(query=q, count=c) for q, c in results]


@router.delete("/recent")
async def clear_recent_searches(
    search_id: Optional[int] = Query(default=None),
    current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
) -> dict:
    service = SearchService(session, current_user, tenant)
    await service.delete_search_history(search_id)
    return {"deleted": True}
