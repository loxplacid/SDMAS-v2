"""Double-entry ledger — FastAPI router (TASK 16).

Every endpoint is permission-gated (``ledger.view`` / ``ledger.create`` /
``ledger.post`` / ``ledger.manage``), tenant-scoped through
``require_tenant_context`` + ``effective_campus_id``, and audit-attributed
through the typed ``AuditActor``.  The accounting-period lock is enforced
in the service: posting into a closed period is impossible regardless of
how the request arrives.
"""

from __future__ import annotations

from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PaginationParams
from app.domains.audit.actors import AuditActor
from app.domains.auth.dependencies import require_permission
from app.domains.auth.models import User
from app.domains.auth.permissions import (
    LEDGER_CREATE,
    LEDGER_MANAGE,
    LEDGER_POST,
    LEDGER_VIEW,
)
from app.domains.ledger.schemas import (
    AccountCreate,
    AccountPage,
    AccountResponse,
    AccountUpdate,
    EntryVerification,
    JournalEntryCreate,
    JournalEntryPage,
    JournalEntryResponse,
    PeriodCreate,
    PeriodPage,
    PeriodResponse,
    ReversalCreate,
    TrialBalanceResponse,
)
from app.domains.ledger.service import LedgerService
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import effective_campus_id
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/ledger", tags=["ledger"])


async def get_ledger_svc(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> LedgerService:
    return LedgerService(session, tenant)


def _actor(user: User) -> AuditActor:
    return AuditActor.user(user.id, user.username)


# ======================================================================
# Chart of accounts
# ======================================================================


@router.get("/accounts", response_model=AccountPage)
async def list_accounts(
    pagination: PaginationParams = Depends(),
    account_type: Optional[str] = Query(None, alias="account_type"),
    active_only: bool = Query(False, alias="active_only"),
    svc: LedgerService = Depends(get_ledger_svc),
    _actor_user: User = Depends(require_permission(LEDGER_VIEW)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> AccountPage:
    items, total = await svc.list_accounts(
        account_type=account_type,
        active_only=active_only,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return AccountPage.create(
        [AccountResponse.model_validate(a) for a in items],
        total,
        pagination.page,
        pagination.size,
    )


@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    data: AccountCreate,
    svc: LedgerService = Depends(get_ledger_svc),
    user: User = Depends(require_permission(LEDGER_MANAGE)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> AccountResponse:
    account = await svc.create_account(data, actor=_actor(user))
    return AccountResponse.model_validate(account)


@router.patch("/accounts/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: int,
    data: AccountUpdate,
    svc: LedgerService = Depends(get_ledger_svc),
    user: User = Depends(require_permission(LEDGER_MANAGE)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> AccountResponse:
    account = await svc.update_account(account_id, data, actor=_actor(user))
    return AccountResponse.model_validate(account)


@router.get("/accounts/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: int,
    svc: LedgerService = Depends(get_ledger_svc),
    _actor_user: User = Depends(require_permission(LEDGER_VIEW)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> AccountResponse:
    account = await svc.get_account(account_id)
    return AccountResponse.model_validate(account)


@router.post("/accounts/seed", response_model=list[AccountResponse])
async def seed_default_chart(
    svc: LedgerService = Depends(get_ledger_svc),
    user: User = Depends(require_permission(LEDGER_MANAGE)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> list[AccountResponse]:
    accounts = await svc.seed_default_chart(actor=_actor(user))
    return [AccountResponse.model_validate(a) for a in accounts]


# ======================================================================
# Accounting periods
# ======================================================================


@router.get("/periods", response_model=PeriodPage)
async def list_periods(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None, alias="status"),
    svc: LedgerService = Depends(get_ledger_svc),
    _actor_user: User = Depends(require_permission(LEDGER_VIEW)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> PeriodPage:
    items, total = await svc.list_periods(
        status=status_filter,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return PeriodPage.create(
        [PeriodResponse.model_validate(p) for p in items],
        total,
        pagination.page,
        pagination.size,
    )


@router.post("/periods", response_model=PeriodResponse, status_code=status.HTTP_201_CREATED)
async def create_period(
    data: PeriodCreate,
    svc: LedgerService = Depends(get_ledger_svc),
    user: User = Depends(require_permission(LEDGER_MANAGE)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> PeriodResponse:
    period = await svc.create_period(data, actor=_actor(user))
    return PeriodResponse.model_validate(period)


@router.post("/periods/{period_id}/close", response_model=PeriodResponse)
async def close_period(
    period_id: int,
    svc: LedgerService = Depends(get_ledger_svc),
    user: User = Depends(require_permission(LEDGER_MANAGE)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> PeriodResponse:
    period = await svc.close_period(period_id, actor=_actor(user))
    return PeriodResponse.model_validate(period)


# ======================================================================
# Journal entries
# ======================================================================


@router.get("/entries", response_model=JournalEntryPage)
async def list_entries(
    pagination: PaginationParams = Depends(),
    period_id: Optional[int] = Query(None, alias="period_id"),
    account_id: Optional[int] = Query(None, alias="account_id"),
    entry_status: Optional[str] = Query(None, alias="status"),
    source_type: Optional[str] = Query(None, alias="source_type"),
    source_id: Optional[str] = Query(None, alias="source_id"),
    from_date: Optional[date_type] = Query(None, alias="from_date"),
    to_date: Optional[date_type] = Query(None, alias="to_date"),
    svc: LedgerService = Depends(get_ledger_svc),
    _actor_user: User = Depends(require_permission(LEDGER_VIEW)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> JournalEntryPage:
    items, total = await svc.list_entries(
        period_id=period_id,
        account_id=account_id,
        status=entry_status,
        source_type=source_type,
        source_id=source_id,
        from_date=from_date,
        to_date=to_date,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return JournalEntryPage.create(
        [JournalEntryResponse.model_validate(e) for e in items],
        total,
        pagination.page,
        pagination.size,
    )


@router.post("/entries/post", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_and_post_entry(
    data: JournalEntryCreate,
    svc: LedgerService = Depends(get_ledger_svc),
    user: User = Depends(require_permission(LEDGER_POST)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> JournalEntryResponse:
    entry = await svc.create_and_post(data, actor=_actor(user))
    return JournalEntryResponse.model_validate(entry)


@router.post("/entries", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_draft_entry(
    data: JournalEntryCreate,
    svc: LedgerService = Depends(get_ledger_svc),
    user: User = Depends(require_permission(LEDGER_CREATE)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> JournalEntryResponse:
    entry = await svc.create_entry(data, actor=_actor(user))
    return JournalEntryResponse.model_validate(entry)


@router.get("/entries/{entry_id}", response_model=JournalEntryResponse)
async def get_entry(
    entry_id: int,
    svc: LedgerService = Depends(get_ledger_svc),
    _actor_user: User = Depends(require_permission(LEDGER_VIEW)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> JournalEntryResponse:
    entry = await svc.get_entry(entry_id)
    return JournalEntryResponse.model_validate(entry)


@router.get("/entries/{entry_id}/verify", response_model=EntryVerification)
async def verify_entry(
    entry_id: int,
    svc: LedgerService = Depends(get_ledger_svc),
    _actor_user: User = Depends(require_permission(LEDGER_VIEW)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> EntryVerification:
    return EntryVerification(**await svc.verify_entry(entry_id))


@router.post("/entries/{entry_id}/post", response_model=JournalEntryResponse)
async def post_entry(
    entry_id: int,
    svc: LedgerService = Depends(get_ledger_svc),
    user: User = Depends(require_permission(LEDGER_POST)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> JournalEntryResponse:
    entry = await svc.post_entry(entry_id, actor=_actor(user))
    return JournalEntryResponse.model_validate(entry)


@router.post("/entries/{entry_id}/reverse", response_model=JournalEntryResponse)
async def reverse_entry(
    entry_id: int,
    data: ReversalCreate,
    svc: LedgerService = Depends(get_ledger_svc),
    user: User = Depends(require_permission(LEDGER_POST)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> JournalEntryResponse:
    entry = await svc.reverse_entry(
        entry_id,
        reason=data.reason,
        actor=_actor(user),
        entry_date=data.entry_date,
        period_id=data.period_id,
    )
    return JournalEntryResponse.model_validate(entry)


# ======================================================================
# Reporting
# ======================================================================


@router.get("/trial-balance", response_model=TrialBalanceResponse)
async def trial_balance(
    period_id: Optional[int] = Query(None, alias="period_id"),
    as_of: Optional[date_type] = Query(None, alias="as_of"),
    svc: LedgerService = Depends(get_ledger_svc),
    _actor_user: User = Depends(require_permission(LEDGER_VIEW)),
    _tenant: TenantContext = Depends(require_tenant_context),
) -> TrialBalanceResponse:
    return await svc.trial_balance(period_id=period_id, as_of=as_of)
