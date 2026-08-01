from __future__ import annotations

import datetime
import secrets
import uuid
from typing import Any, Optional

from sqlalchemy import func, select, update, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.domains.documents.constants import (
    AUDIT_DOCUMENT_ARCHIVE,
    AUDIT_DOCUMENT_CREATE,
    AUDIT_DOCUMENT_DELETE,
    AUDIT_DOCUMENT_DOWNLOAD,
    AUDIT_DOCUMENT_SHARE,
    AUDIT_DOCUMENT_UPDATE,
    AUDIT_DOCUMENT_VERSION,
    BUILTIN_CATEGORIES,
    CATEGORY_STAFF,
    CATEGORY_STUDENT,
    LIFECYCLE_ACTIVE,
    LIFECYCLE_ARCHIVED,
    LIFECYCLE_DELETED,
    LIFECYCLE_DRAFT,
    VALID_LIFECYCLE_TRANSITIONS,
)
from app.domains.documents.models import Document, DocumentCategory, DocumentShare, DocumentVersion
from app.domains.documents.storage import get_storage_backend
from app.domains.documents.validation import validate_and_prepare_file, VirusScanner
from app.domains.auth.models import User


def _make_storage_key(category_code: str, ext: str) -> str:
    today = datetime.date.today()
    return f"{category_code}/{today.year}/{today.month:02d}/{uuid.uuid4().hex}{ext}"


def _check_role_access(category: DocumentCategory, user: User) -> None:
    if not any(role in category.allowed_roles for role in user.role_codes):
        raise AuthorizationError(f"Access denied for category '{category.code}'")


def _check_owner_access(doc: Document, user: User, category: DocumentCategory) -> None:
    if "admin" in user.role_codes:
        return
    if doc.owner_id == user.id:
        return
    if category.owner_type == "student" and doc.student_id:
        return
    raise AuthorizationError("Access denied to this document")


def _validate_lifecycle_transition(current: str, target: str) -> None:
    if target not in VALID_LIFECYCLE_TRANSITIONS.get(current, []):
        raise ValidationError(f"Cannot transition from '{current}' to '{target}'")


class DocumentCategoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def seed_categories(self) -> None:
        for cat in BUILTIN_CATEGORIES:
            existing = await self.session.execute(
                select(DocumentCategory).where(DocumentCategory.code == cat["code"])
            )
            if not existing.scalar_one_or_none():
                self.session.add(DocumentCategory(**cat))
        await self.session.commit()

    async def list_active(self) -> list[DocumentCategory]:
        result = await self.session.execute(
            select(DocumentCategory).where(DocumentCategory.is_active == True).order_by(DocumentCategory.name)
        )
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> DocumentCategory:
        result = await self.session.execute(
            select(DocumentCategory).where(DocumentCategory.code == code)
        )
        cat = result.scalar_one_or_none()
        if not cat:
            raise NotFoundError(f"Document category '{code}' not found")
        return cat

    async def get(self, category_id: int) -> DocumentCategory:
        cat = await self.session.get(DocumentCategory, category_id)
        if not cat:
            raise NotFoundError("Document category not found")
        return cat


class DocumentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.storage = get_storage_backend()
        self.category_service = DocumentCategoryService(session)

    async def upload(
        self,
        file_data: bytes,
        filename: str,
        category_id: int,
        user: User,
        student_id: Optional[int] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        request: Any = None,
        campus_id: Optional[int] = None,
    ) -> Document:
        category = await self.category_service.get(category_id)
        _check_role_access(category, user)

        mime_type, ext = validate_and_prepare_file(file_data, filename)
        await VirusScanner.scan(file_data)

        storage_key = _make_storage_key(category.code, ext)
        await self.storage.upload(file_data, storage_key, mime_type)

        doc = Document(
            category_id=category.id,
            owner_id=user.id,
            owner_type=category.owner_type,
            student_id=student_id,
            original_filename=filename,
            storage_key=storage_key,
            mime_type=mime_type,
            file_size=len(file_data),
            title=title or filename,
            description=description,
            tags=tags,
            lifecycle_state=LIFECYCLE_ACTIVE,
            campus_id=campus_id if campus_id is not None else getattr(user, "campus_id", None),
            uploaded_by=user.id,
        )
        self.session.add(doc)
        await self.session.commit()
        await self.session.refresh(doc)
        await self._audit(AUDIT_DOCUMENT_CREATE, doc, user, request, {"file_size": len(file_data), "mime_type": mime_type})

        doc_id = doc.id
        ver = DocumentVersion(
            document_id=doc_id,
            version_number=1,
            storage_key=storage_key,
            original_filename=filename,
            mime_type=mime_type,
            file_size=len(file_data),
            uploaded_by=user.id,
            change_notes="Initial upload",
        )
        self.session.add(ver)
        await self.session.commit()
        return doc

    async def list(
        self,
        user: User,
        category_id: Optional[int] = None,
        category_code: Optional[str] = None,
        student_id: Optional[int] = None,
        lifecycle_state: Optional[str] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Document], int]:
        conditions = [Document.deleted_at.is_(None)]

        if category_id:
            conditions.append(Document.category_id == category_id)
        if category_code:
            cat = await self.category_service.get_by_code(category_code)
            conditions.append(Document.category_id == cat.id)
        if student_id:
            conditions.append(Document.student_id == student_id)
        if lifecycle_state:
            conditions.append(Document.lifecycle_state == lifecycle_state)
        if campus_id is not None:
            conditions.append(Document.campus_id == campus_id)

        if "admin" not in user.role_codes:
            conditions.append(Document.owner_id == user.id)

        query = (
            select(Document)
            .where(*conditions)
            .options(selectinload(Document.versions), selectinload(Document.shares))
            .offset(skip)
            .limit(limit)
            .order_by(Document.uploaded_at.desc())
        )
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        count_query = select(func.count(Document.id)).where(*conditions)
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0
        return items, total

    async def get(self, doc_id: int, user: User) -> Document:
        doc = await self.session.get(
            Document, doc_id,
            options=[selectinload(Document.category), selectinload(Document.versions), selectinload(Document.shares)],
        )
        if not doc or doc.deleted_at is not None:
            raise NotFoundError("Document not found")
        _check_owner_access(doc, user, doc.category)
        return doc

    async def update_metadata(self, doc_id: int, user: User, data: Any, request: Any = None) -> Document:
        doc = await self.get(doc_id, user)
        update_data = data.model_dump(exclude_unset=True)

        if "lifecycle_state" in update_data:
            _validate_lifecycle_transition(doc.lifecycle_state, update_data["lifecycle_state"])
            if update_data["lifecycle_state"] == LIFECYCLE_ARCHIVED:
                doc.archived_at = datetime.datetime.now(datetime.timezone.utc)
            if update_data["lifecycle_state"] == LIFECYCLE_DELETED:
                doc.deleted_at = datetime.datetime.now(datetime.timezone.utc)

        for key, value in update_data.items():
            if key != "lifecycle_state":
                setattr(doc, key, value)

        await self.session.commit()
        await self.session.refresh(doc)
        await self._audit(AUDIT_DOCUMENT_UPDATE, doc, user, request, {"changes": update_data})
        return doc

    async def delete(self, doc_id: int, user: User, request: Any = None) -> None:
        doc = await self.get(doc_id, user)
        _validate_lifecycle_transition(doc.lifecycle_state, LIFECYCLE_DELETED)
        doc.lifecycle_state = LIFECYCLE_DELETED
        doc.deleted_at = datetime.datetime.now(datetime.timezone.utc)
        await self.session.commit()
        await self._audit(AUDIT_DOCUMENT_DELETE, doc, user, request)

    async def hard_delete(self, doc_id: int, user: User) -> None:
        if "admin" not in user.role_codes:
            raise AuthorizationError("Only admins can permanently delete documents")
        doc = await self.session.get(Document, doc_id)
        if not doc:
            raise NotFoundError("Document not found")
        await self.storage.delete(doc.storage_key)
        await self.session.delete(doc)
        await self.session.commit()

    async def download(self, doc_id: int, user: User, request: Any = None) -> tuple[bytes, str, str]:
        doc = await self.get(doc_id, user)
        file_data = await self.storage.download(doc.storage_key)
        await self._audit(AUDIT_DOCUMENT_DOWNLOAD, doc, user, request)
        return file_data, doc.original_filename, doc.mime_type

    async def add_version(
        self,
        doc_id: int,
        file_data: bytes,
        filename: str,
        user: User,
        change_notes: Optional[str] = None,
        request: Any = None,
    ) -> DocumentVersion:
        doc = await self.get(doc_id, user)
        mime_type, ext = validate_and_prepare_file(file_data, filename)
        await VirusScanner.scan(file_data)

        max_ver = await self.session.execute(
            select(func.max(DocumentVersion.version_number)).where(DocumentVersion.document_id == doc_id)
        )
        next_ver = (max_ver.scalar() or 0) + 1

        storage_key = _make_storage_key(doc.category.code, ext)
        await self.storage.upload(file_data, storage_key, mime_type)

        ver = DocumentVersion(
            document_id=doc_id,
            version_number=next_ver,
            storage_key=storage_key,
            original_filename=filename,
            mime_type=mime_type,
            file_size=len(file_data),
            uploaded_by=user.id,
            change_notes=change_notes,
        )
        self.session.add(ver)

        doc.original_filename = filename
        doc.storage_key = storage_key
        doc.mime_type = mime_type
        doc.file_size = len(file_data)
        doc.updated_at = datetime.datetime.now(datetime.timezone.utc)

        await self.session.commit()
        await self.session.refresh(ver)
        await self._audit(AUDIT_DOCUMENT_VERSION, doc, user, request, {"version": next_ver, "change_notes": change_notes})
        return ver

    async def create_share(
        self, doc_id: int, user: User, expires_in_hours: int = 24, max_downloads: Optional[int] = None, request: Any = None
    ) -> DocumentShare:
        doc = await self.get(doc_id, user)
        token = secrets.token_urlsafe(48)
        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=expires_in_hours)

        signed_url = await self.storage.get_signed_url(doc.storage_key, expires_in=int(expires_in_hours * 3600))

        share = DocumentShare(
            document_id=doc_id,
            token=token,
            expires_at=expires_at,
            max_downloads=max_downloads,
            created_by=user.id,
        )
        self.session.add(share)
        await self.session.commit()
        await self.session.refresh(share)

        await self._audit(AUDIT_DOCUMENT_SHARE, doc, user, request, {"share_id": share.id, "expires_at": expires_at.isoformat()})

        share.signed_url = signed_url
        return share

    async def list_shares(self, doc_id: int, user: User) -> list[DocumentShare]:
        doc = await self.get(doc_id, user)
        result = await self.session.execute(
            select(DocumentShare).where(DocumentShare.document_id == doc_id).order_by(DocumentShare.created_at.desc())
        )
        return list(result.scalars().all())

    async def revoke_share(self, share_id: int, user: User) -> None:
        share = await self.session.get(DocumentShare, share_id, options=[selectinload(DocumentShare.document)])
        if not share:
            raise NotFoundError("Share not found")
        doc = await self.get(share.document_id, user)
        share.is_revoked = True
        await self.session.commit()

    async def _audit(self, action: str, doc: Document, user: User, request: Any = None, extra: Optional[dict] = None) -> None:
        from app.domains.audit.service import AuditService
        from app.domains.audit.utils import get_request_metadata

        metadata = get_request_metadata(request) if request else {}
        details = {
            "document_id": doc.id,
            "filename": doc.original_filename,
            "category_id": doc.category_id,
            "file_size": doc.file_size,
            **(extra or {}),
        }
        await AuditService(self.session).record(
            action=action,
            resource_type="document",
            resource_id=str(doc.id),
            details=details,
            user_id=user.id,
            username=user.username if hasattr(user, "username") else None,
            **metadata,
        )
