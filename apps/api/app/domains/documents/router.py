from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PaginationParams
from app.domains.auth.dependencies import get_current_user, require_role
from app.domains.auth.models import User
from app.domains.documents.constants import BUILTIN_CATEGORIES
from app.domains.documents.models import DocumentShare
from app.domains.documents.schemas import (
    DocumentCategoryResponse,
    DocumentCreate,
    DocumentPage,
    DocumentResponse,
    DocumentShareCreate,
    DocumentShareResponse,
    DocumentUpdate,
    DocumentUploadResponse,
    DocumentVersionResponse,
)
from app.domains.documents.service import DocumentCategoryService, DocumentService
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import assert_tenant_scope, effective_campus_id
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/documents", tags=["documents"])


async def get_cat_svc(session: AsyncSession = Depends(get_session)) -> DocumentCategoryService:
    return DocumentCategoryService(session)


async def get_doc_svc(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> DocumentService:
    return DocumentService(session, tenant)


# ── Categories ──


@router.get("/categories", response_model=list[DocumentCategoryResponse])
async def list_categories(
    svc: DocumentCategoryService = Depends(get_cat_svc),
    _user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
) -> list[DocumentCategoryResponse]:
    return [DocumentCategoryResponse.model_validate(c) for c in await svc.list_active()]


# ── Upload ──


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    category_id: int = Query(...),
    student_id: Optional[int] = Query(None),
    title: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
    tags: Optional[str] = Query(None),
    request: Request = None,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant")),
    svc: DocumentService = Depends(get_doc_svc),
    tenant: TenantContext = Depends(require_tenant_context),
) -> DocumentUploadResponse:
    file_data = await file.read()
    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    doc = await svc.upload(
        file_data=file_data,
        filename=file.filename or "unnamed",
        category_id=category_id,
        user=current_user,
        student_id=student_id,
        title=title,
        description=description,
        tags=tag_list,
        request=request,
        campus_id=tenant.campus_id if tenant.is_tenant_scoped else None,
    )

    from app.domains.documents.storage import get_storage_backend
    storage = get_storage_backend()
    download_url = await storage.get_signed_url(doc.storage_key, expires_in=3600)

    return DocumentUploadResponse(
        id=doc.id,
        filename=doc.original_filename,
        mime_type=doc.mime_type,
        file_size=doc.file_size,
        title=doc.title,
        storage_key=doc.storage_key,
        uploaded_at=doc.uploaded_at,
        download_url=download_url,
    )


# ── CRUD ──


@router.get("", response_model=DocumentPage)
async def list_documents(
    pagination: PaginationParams = Depends(),
    category_id: Optional[int] = Query(None),
    category_code: Optional[str] = Query(None),
    student_id: Optional[int] = Query(None),
    lifecycle_state: Optional[str] = Query(None),
    campus_id: Optional[int] = Query(default=None, alias="campus_id"),
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
    svc: DocumentService = Depends(get_doc_svc),
    tenant: TenantContext = Depends(require_tenant_context),
) -> DocumentPage:
    effective_campus = effective_campus_id(tenant, campus_id)
    items, total = await svc.list(
        user=current_user,
        category_id=category_id,
        category_code=category_code,
        student_id=student_id,
        lifecycle_state=lifecycle_state,
        campus_id=effective_campus,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    result_items = []
    for doc in items:
        d = DocumentResponse.model_validate(doc)
        if doc.versions:
            d.current_version = DocumentVersionResponse.model_validate(doc.versions[-1])
        d.share_count = len([s for s in doc.shares if not s.is_revoked])
        result_items.append(d)
    return Page.create(items=result_items, total=total, page=pagination.page, size=pagination.size)


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: int,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
    svc: DocumentService = Depends(get_doc_svc),
    tenant: TenantContext = Depends(require_tenant_context),
) -> DocumentResponse:
    doc = await svc.get(doc_id, current_user)
    assert_tenant_scope(doc, tenant, resource="document")
    resp = DocumentResponse.model_validate(doc)
    if doc.versions:
        resp.current_version = DocumentVersionResponse.model_validate(doc.versions[-1])
    resp.share_count = len([s for s in doc.shares if not s.is_revoked])
    return resp


@router.patch("/{doc_id}", response_model=DocumentResponse)
async def update_document(
    doc_id: int,
    data: DocumentUpdate,
    request: Request = None,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant")),
    svc: DocumentService = Depends(get_doc_svc),
    tenant: TenantContext = Depends(require_tenant_context),
) -> DocumentResponse:
    existing = await svc.get(doc_id, current_user)
    assert_tenant_scope(existing, tenant, resource="document")
    doc = await svc.update_metadata(doc_id, current_user, data, request=request)
    resp = DocumentResponse.model_validate(doc)
    if doc.versions:
        resp.current_version = DocumentVersionResponse.model_validate(doc.versions[-1])
    resp.share_count = len([s for s in doc.shares if not s.is_revoked])
    return resp


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: int,
    request: Request = None,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant")),
    svc: DocumentService = Depends(get_doc_svc),
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    existing = await svc.get(doc_id, current_user)
    assert_tenant_scope(existing, tenant, resource="document")
    await svc.delete(doc_id, current_user, request=request)


# ── Download ──


@router.get("/{doc_id}/download")
async def download_document(
    doc_id: int,
    request: Request = None,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
    svc: DocumentService = Depends(get_doc_svc),
    tenant: TenantContext = Depends(require_tenant_context),
) -> Response:
    existing = await svc.get(doc_id, current_user)
    assert_tenant_scope(existing, tenant, resource="document")
    file_data, filename, mime_type = await svc.download(doc_id, current_user, request=request)
    return Response(
        content=file_data,
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Versions ──


@router.post("/{doc_id}/versions", response_model=DocumentVersionResponse, status_code=status.HTTP_201_CREATED)
async def add_document_version(
    doc_id: int,
    file: UploadFile,
    change_notes: Optional[str] = Query(None),
    request: Request = None,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant")),
    svc: DocumentService = Depends(get_doc_svc),
    tenant: TenantContext = Depends(require_tenant_context),
) -> DocumentVersionResponse:
    existing = await svc.get(doc_id, current_user)
    assert_tenant_scope(existing, tenant, resource="document")
    file_data = await file.read()
    ver = await svc.add_version(
        doc_id, file_data, file.filename or "unnamed", current_user,
        change_notes=change_notes, request=request,
    )
    return DocumentVersionResponse.model_validate(ver)


@router.get("/{doc_id}/versions", response_model=list[DocumentVersionResponse])
async def list_document_versions(
    doc_id: int,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
    svc: DocumentService = Depends(get_doc_svc),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[DocumentVersionResponse]:
    doc = await svc.get(doc_id, current_user)
    assert_tenant_scope(doc, tenant, resource="document")
    return [DocumentVersionResponse.model_validate(v) for v in doc.versions]


# ── Shares ──


@router.post("/{doc_id}/shares", response_model=DocumentShareResponse, status_code=status.HTTP_201_CREATED)
async def create_document_share(
    doc_id: int,
    data: DocumentShareCreate,
    request: Request = None,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant")),
    svc: DocumentService = Depends(get_doc_svc),
    tenant: TenantContext = Depends(require_tenant_context),
) -> DocumentShareResponse:
    existing = await svc.get(doc_id, current_user)
    assert_tenant_scope(existing, tenant, resource="document")
    share = await svc.create_share(
        doc_id, current_user,
        expires_in_hours=data.expires_in_hours,
        max_downloads=data.max_downloads,
        request=request,
    )
    return DocumentShareResponse.model_validate(share)


@router.get("/{doc_id}/shares", response_model=list[DocumentShareResponse])
async def list_document_shares(
    doc_id: int,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
    svc: DocumentService = Depends(get_doc_svc),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[DocumentShareResponse]:
    existing = await svc.get(doc_id, current_user)
    assert_tenant_scope(existing, tenant, resource="document")
    from app.domains.documents.storage import get_storage_backend
    storage = get_storage_backend()
    shares = await svc.list_shares(doc_id, current_user)
    result = []
    for s in shares:
        sr = DocumentShareResponse.model_validate(s)
        if not s.is_revoked and s.expires_at > datetime.datetime.now(datetime.timezone.utc):
            sr.signed_url = await storage.get_signed_url(
                s.document.storage_key,
                expires_in=int((s.expires_at - datetime.datetime.now(datetime.timezone.utc)).total_seconds()),
            )
        result.append(sr)
    return result


@router.post("/shares/{share_id}/revoke", response_model=DocumentShareResponse)
async def revoke_document_share(
    share_id: int,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant")),
    svc: DocumentService = Depends(get_doc_svc),
    tenant: TenantContext = Depends(require_tenant_context),
) -> DocumentShareResponse:
    share = await svc.session.get(DocumentShare, share_id)
    if share is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Document share {share_id} not found")
    existing = await svc.get(share.document_id, current_user)
    assert_tenant_scope(existing, tenant, resource="document")
    await svc.revoke_share(share_id, current_user)
    share = await svc.session.get(DocumentShare, share_id)
    return DocumentShareResponse.model_validate(share)
