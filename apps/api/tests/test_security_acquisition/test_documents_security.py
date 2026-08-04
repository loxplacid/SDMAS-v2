"""Document-domain security tests.

Proves at the API layer:

* unauthenticated download → 401 (auth gate)
* cross-tenant download / update / delete / share-revoke → 403/404
* oversized upload → rejected
* content that is not an allowed MIME type (even with a trusted extension)
  → rejected (magic-based content sniffing, not extension trust)
* disallowed/malicious extensions → rejected
* path-traversal filenames cannot escape the storage root (server-generated
  UUID storage keys + extension allowlist)
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.domains.documents.models import Document, DocumentCategory, DocumentShare

from .conftest import AcqEnv, seed_document

pytestmark = pytest.mark.asyncio

PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<<>>\n%%EOF"
EXE_BYTES = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00" + b"\x00" * 64


@pytest_asyncio.fixture(autouse=True)
def _deterministic_mime_detector(monkeypatch):
    """Pin MIME detection to a deterministic stub for the upload tests.

    The production detector uses ``python-magic`` (libmagic DLL), which is
    flaky on Windows dev machines — loading the DLL inside the event loop
    (after aiosqlite worker threads exist) can raise a native access
    violation and crash the whole test process.  The security property
    under test is the VALIDATION GATE (extension allowlist + content-based
    MIME rejection + size cap), not libmagic itself, so the detector is
    stubbed with identical classification semantics:

    * ``%PDF`` content  → ``application/pdf`` (allowed)
    * ``MZ`` content    → ``application/x-dosexec`` (rejected)
    * anything else     → ``application/octet-stream`` (rejected)
    """

    def _fake_detect(file_data: bytes) -> str:
        if file_data.startswith(b"%PDF"):
            return "application/pdf"
        if file_data.startswith(b"MZ"):
            return "application/x-dosexec"
        return "application/octet-stream"

    monkeypatch.setattr(
        "app.domains.documents.validation.FileValidator.detect_mime_type",
        staticmethod(_fake_detect),
    )


async def _seed_category(factory, code: str = "acq-docs") -> int:
    async with factory() as s:
        cat = DocumentCategory(code=code, name="Acquisition Docs")
        s.add(cat)
        await s.commit()
        return cat.id


async def _upload(
    env: AcqEnv,
    headers: dict[str, str],
    category_id: int,
    filename: str,
    content: bytes,
):
    return await env.client.post(
        "/api/documents/upload",
        params={"category_id": category_id},
        files={"file": (filename, content, "application/octet-stream")},
        headers=headers,
    )


async def test_unauthorized_download_rejected(acq_env: AcqEnv, headers_a):
    """Invariant: downloading without a token is rejected by the auth gate
    (document URLs are never anonymously accessible)."""
    doc_id = await seed_document(acq_env.factory, 1, 1, "acq-unauth")
    resp = await acq_env.client.get(f"/api/documents/{doc_id}/download")
    assert resp.status_code == 401, resp.text


async def test_cross_tenant_download_denied(
    acq_env: AcqEnv, headers_a, headers_b
):
    """Invariant: tenant A cannot download tenant B's document — even with
    the exact ID (IDOR on document downloads). Uploads are end-to-end so
    the storage side is exercised too."""
    category_id = await _seed_category(acq_env.factory, "acq-xdl")

    # B uploads a real document (campus-tagged + stored on disk).
    resp = await _upload(
        acq_env, headers_b, category_id, "b-secret.pdf", PDF_BYTES
    )
    assert resp.status_code == 201, resp.text
    b_doc = resp.json()["id"]

    # A uploads its own document.
    resp = await _upload(
        acq_env, headers_a, category_id, "a-visible.pdf", PDF_BYTES
    )
    assert resp.status_code == 201, resp.text
    a_doc = resp.json()["id"]

    # A cannot download B's document — exact-ID IDOR.
    resp = await acq_env.client.get(
        f"/api/documents/{b_doc}/download", headers=headers_a
    )
    assert resp.status_code in (403, 404), resp.text

    # B can download its own.
    resp = await acq_env.client.get(
        f"/api/documents/{b_doc}/download", headers=headers_b
    )
    assert resp.status_code == 200, resp.text

    # A can download its own.
    resp = await acq_env.client.get(
        f"/api/documents/{a_doc}/download", headers=headers_a
    )
    assert resp.status_code == 200, resp.text


async def test_cross_tenant_document_mutation_denied(
    acq_env: AcqEnv, headers_a
):
    """Invariant: tenant A cannot update, delete, or version tenant B's
    document."""
    b_doc = await seed_document(acq_env.factory, 2, 2, "acq-x-mut")

    resp = await acq_env.client.patch(
        f"/api/documents/{b_doc}", json={"title": "Hijacked"},
        headers=headers_a,
    )
    assert resp.status_code in (403, 404), resp.text

    resp = await acq_env.client.delete(
        f"/api/documents/{b_doc}", headers=headers_a
    )
    assert resp.status_code in (403, 404), resp.text

    resp = await acq_env.client.post(
        f"/api/documents/{b_doc}/versions",
        params={"change_notes": "x"},
        files={"file": ("v2.pdf", PDF_BYTES, "application/pdf")},
        headers=headers_a,
    )
    assert resp.status_code in (403, 404), resp.text


async def test_cross_tenant_share_revoke_denied(acq_env: AcqEnv, headers_a):
    """Invariant: tenant A cannot revoke a share on tenant B's document."""
    import datetime

    b_doc = await seed_document(acq_env.factory, 2, 2, "acq-x-share")
    async with acq_env.factory() as s:
        share = DocumentShare(
            document_id=b_doc,
            token="acq-share-token-xyz",
            created_by=2,
            expires_at=datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=1),
            max_downloads=None,
        )
        s.add(share)
        await s.commit()
        share_id = share.id

    resp = await acq_env.client.post(
        f"/api/documents/shares/{share_id}/revoke", headers=headers_a
    )
    assert resp.status_code in (403, 404), resp.text

    # The share is still active (not revoked by A).
    async with acq_env.factory() as s:
        share = (await s.execute(
            select(DocumentShare).where(DocumentShare.id == share_id)
        )).scalar_one()
    assert not share.is_revoked


async def test_oversized_upload_rejected(
    acq_env: AcqEnv, headers_a
):
    """Invariant: files above the configured size cap are rejected before
    storage (20 MB default)."""
    category_id = await _seed_category(acq_env.factory, "acq-big")
    big = PDF_BYTES + b"0" * (21 * 1024 * 1024)
    resp = await _upload(
        acq_env, headers_a, category_id, "big.pdf", big
    )
    assert resp.status_code == 400, resp.text


async def test_invalid_mime_content_rejected(
    acq_env: AcqEnv, headers_a
):
    """Invariant: a file whose CONTENT is an executable is rejected even
    when the extension claims PDF — MIME detection is content-based, so
    disguised executables cannot be uploaded."""
    category_id = await _seed_category(acq_env.factory, "acq-mime")
    resp = await _upload(
        acq_env, headers_a, category_id, "innocent.pdf", EXE_BYTES
    )
    assert resp.status_code == 400, resp.text


async def test_disallowed_extension_rejected(
    acq_env: AcqEnv, headers_a
):
    """Invariant: executables / scripts / web pages are rejected by
    extension allowlist regardless of content."""
    category_id = await _seed_category(acq_env.factory, "acq-ext")
    for filename in ("evil.exe", "payload.sh", "xss.html", "app.js"):
        resp = await _upload(
            acq_env, headers_a, category_id, filename, b"dummy"
        )
        assert resp.status_code == 400, f"{filename}: {resp.status_code}"


async def test_path_traversal_filename_rejected(
    acq_env: AcqEnv, headers_a
):
    """Invariant: traversal-style filenames are rejected (their extensions
    are not in the allowlist)."""
    category_id = await _seed_category(acq_env.factory, "acq-trav")
    for filename in ("../../etc/passwd", "..\\..\\windows\\system32\\config"):
        resp = await _upload(
            acq_env, headers_a, category_id, filename, b"dummy"
        )
        assert resp.status_code == 400, f"{filename}: {resp.status_code}"


async def test_upload_uses_server_generated_storage_key(
    acq_env: AcqEnv, headers_a
):
    """Invariant: even a traversal-looking filename with an allowed
    extension cannot escape the storage root — the storage key is a
    server-generated UUID, never derived from user input."""
    category_id = await _seed_category(acq_env.factory, "acq-key")
    resp = await _upload(
        acq_env, headers_a, category_id, "../../secret.pdf", PDF_BYTES
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    # storage key is a UUID under the category path, never user-controlled.
    key = body["storage_key"]
    assert ".." not in key
    assert key.startswith("acq-key/")
    assert key.endswith(".pdf")
    assert body["filename"] == "../../secret.pdf"

    # The file is still downloadable through the server-owned key.
    dl = await acq_env.client.get(
        f"/api/documents/{body['id']}/download", headers=headers_a
    )
    assert dl.status_code == 200, dl.text


async def test_valid_pdf_upload_succeeds(acq_env: AcqEnv, headers_a):
    """Positive control: a legitimate PDF upload passes all checks."""
    category_id = await _seed_category(acq_env.factory, "acq-ok")
    resp = await _upload(
        acq_env, headers_a, category_id, "report.pdf", PDF_BYTES
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["mime_type"] == "application/pdf"
