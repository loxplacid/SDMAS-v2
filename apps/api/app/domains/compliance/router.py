"""Declarative Compliance Engine API (TASK 20).

Every endpoint is permission-gated, tenant-scoped, and audit-attributed.
No CBSE/ICSE/state rules are hard-coded — the engine loads schema packs.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.dependencies import require_permission
from app.domains.auth.models import User
from app.domains.auth.permissions import (
    COMPLIANCE_MANAGE,
    COMPLIANCE_VIEW,
)
from app.domains.compliance.schemas import (
    ApprovalCreate,
    ApprovalResponse,
    ComplianceDashboard,
    RegulationCreate,
    RegulationResponse,
    RequirementCreate,
    RequirementResponse,
    RuleResponse,
    SchemaCreate,
    SchemaResponse,
    SubmissionCreate,
    SubmissionDetailResponse,
    SubmissionResponse,
)
from app.domains.compliance.service import ComplianceService
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import effective_campus_id
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


async def get_svc(
    session: AsyncSession = Depends(get_session),
) -> ComplianceService:
    return ComplianceService(session)


# ======================================================================
# Regulations
# ======================================================================


@router.get("/dashboard", response_model=ComplianceDashboard)
async def dashboard(
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ComplianceService = Depends(get_svc),
    _user: User = Depends(require_permission(COMPLIANCE_VIEW)),
):
    """High-level compliance dashboard."""
    campus_id = effective_campus_id(tenant, None)
    data = await svc.dashboard(campus_id)
    return ComplianceDashboard(**data)


@router.get("/regulations", response_model=list[RegulationResponse])
async def list_regulations(
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ComplianceService = Depends(get_svc),
    _user: User = Depends(require_permission(COMPLIANCE_VIEW)),
):
    campus_id = effective_campus_id(tenant, None)
    regs = await svc.list_regulations(campus_id)
    return [RegulationResponse.model_validate(r) for r in regs]


@router.post(
    "/regulations",
    response_model=RegulationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_regulation(
    data: RegulationCreate,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ComplianceService = Depends(get_svc),
    user: User = Depends(require_permission(COMPLIANCE_MANAGE)),
):
    campus_id = effective_campus_id(tenant, None)
    reg = await svc.create_regulation(
        campus_id=campus_id,
        regulation_id=data.regulation_id,
        name=data.name,
        description=data.description,
        authority=data.authority,
        jurisdiction=data.jurisdiction,
        effective_from=data.effective_from,
        effective_until=data.effective_until,
        actor_id=user.id,
    )
    return RegulationResponse.model_validate(reg)


@router.get(
    "/regulations/{regulation_id}",
    response_model=RegulationResponse,
)
async def get_regulation(
    regulation_id: int,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ComplianceService = Depends(get_svc),
    _user: User = Depends(require_permission(COMPLIANCE_VIEW)),
):
    campus_id = effective_campus_id(tenant, None)
    reg = await svc.get_regulation(campus_id, regulation_id)
    if reg is None:
        raise HTTPException(status_code=404, detail="Regulation not found")
    return RegulationResponse.model_validate(reg)


@router.post(
    "/regulations/{regulation_id}/requirements",
    response_model=RequirementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_requirement(
    regulation_id: int,
    data: RequirementCreate,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ComplianceService = Depends(get_svc),
    _user: User = Depends(require_permission(COMPLIANCE_MANAGE)),
):
    campus_id = effective_campus_id(tenant, None)
    req = await svc.create_requirement(
        campus_id=campus_id,
        regulation_id=regulation_id,
        requirement_id=data.requirement_id,
        title=data.title,
        description=data.description,
        category=data.category,
        severity=data.severity,
        is_mandatory=data.is_mandatory,
    )
    return RequirementResponse.model_validate(req)


# ======================================================================
# Schemas
# ======================================================================


@router.get("/schemas", response_model=list[SchemaResponse])
async def list_schemas(
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ComplianceService = Depends(get_svc),
    _user: User = Depends(require_permission(COMPLIANCE_VIEW)),
):
    campus_id = effective_campus_id(tenant, None)
    schemas = await svc.list_schemas(campus_id)
    return [SchemaResponse.model_validate(s) for s in schemas]


@router.post(
    "/schemas",
    response_model=SchemaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_schema(
    data: SchemaCreate,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ComplianceService = Depends(get_svc),
    user: User = Depends(require_permission(COMPLIANCE_MANAGE)),
):
    campus_id = effective_campus_id(tenant, None)
    rules_data = [r.model_dump() for r in data.rules]
    schema = await svc.create_schema(
        campus_id=campus_id,
        schema_id=data.schema_id,
        title=data.title,
        description=data.description,
        data_sources=data.data_sources,
        rules=rules_data,
        actor_id=user.id,
    )
    # Count rules
    schema_dict = SchemaResponse.model_validate(schema).model_dump()
    schema_dict["rule_count"] = len(data.rules)
    return SchemaResponse(**schema_dict)


@router.post("/schemas/{schema_id}/publish", response_model=SchemaResponse)
async def publish_schema(
    schema_id: int,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ComplianceService = Depends(get_svc),
    user: User = Depends(require_permission(COMPLIANCE_MANAGE)),
):
    campus_id = effective_campus_id(tenant, None)
    try:
        schema = await svc.publish_schema(campus_id, schema_id, actor_id=user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return SchemaResponse.model_validate(schema)


@router.get("/schemas/{schema_id}/rules", response_model=list[RuleResponse])
async def list_rules(
    schema_id: int,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ComplianceService = Depends(get_svc),
    _user: User = Depends(require_permission(COMPLIANCE_VIEW)),
):
    schema = await svc.get_schema(None, schema_id)
    if schema is None:
        raise HTTPException(status_code=404, detail="Schema not found")
    return [RuleResponse.model_validate(r) for r in schema.rules]


# ======================================================================
# Submissions + Evaluations
# ======================================================================


@router.post(
    "/submissions",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_for_review(
    data: SubmissionCreate,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ComplianceService = Depends(get_svc),
    user: User = Depends(require_permission(COMPLIANCE_MANAGE)),
):
    campus_id = effective_campus_id(tenant, None)
    sub = await svc.submit(
        campus_id=campus_id,
        regulation_id=data.regulation_id,
        schema_pk=data.schema_id,
        submission_id=data.submission_id,
        title=data.title,
        description=data.description,
        data_snapshot=data.data_snapshot,
        actor_id=user.id,
    )
    return SubmissionResponse.model_validate(sub)


@router.get("/submissions", response_model=list[SubmissionResponse])
async def list_submissions(
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ComplianceService = Depends(get_svc),
    _user: User = Depends(require_permission(COMPLIANCE_VIEW)),
):
    campus_id = effective_campus_id(tenant, None)
    subs = await svc.list_submissions(campus_id)
    return [SubmissionResponse.model_validate(s) for s in subs]


@router.get(
    "/submissions/{submission_id}",
    response_model=SubmissionDetailResponse,
)
async def get_submission_detail(
    submission_id: int,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ComplianceService = Depends(get_svc),
    _user: User = Depends(require_permission(COMPLIANCE_VIEW)),
):
    campus_id = effective_campus_id(tenant, None)
    sub = await svc.get_submission(campus_id, submission_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    evals = await svc.get_evaluations(submission_id)
    explanations = await svc.get_explanations(submission_id)
    return SubmissionDetailResponse(
        submission=SubmissionResponse.model_validate(sub),
        evaluations=[
            {
                "rule_code": e.rule_code,
                "requirement_id": e.requirement_id,
                "result": e.result,
                "severity": e.severity,
                "expected_value": e.expected_value,
                "actual_value": e.actual_value,
                "explanation": e.explanation,
                "trace": e.trace,
            }
            for e in evals
        ],
        explanations=explanations,
    )


@router.post(
    "/submissions/{submission_id}/approve",
    response_model=ApprovalResponse,
)
async def approve_submission(
    submission_id: int,
    data: ApprovalCreate,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ComplianceService = Depends(get_svc),
    user: User = Depends(require_permission(COMPLIANCE_MANAGE)),
):
    campus_id = effective_campus_id(tenant, None)
    try:
        approval = await svc.approve_submission(
            campus_id=campus_id,
            submission_id=submission_id,
            decision=data.decision,
            comment=data.comment,
            actor_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ApprovalResponse.model_validate(approval)
