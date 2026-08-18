"""Tamper-evident audit chain (platform).

A chained cryptographic integrity layer over the existing audit domain
(``app/domains/audit``).  Every audit event gets a chain entry that
references:

- ``prev_hash``    — the previous entry's current hash (the link)
- ``payload_hash`` — a canonical hash of the audit event's content
- ``current_hash`` — ``chain_hash(prev_hash, payload_hash, campus, index)``
- ``signature``    — HMAC-SHA256 over the current hash (server secret)

Periodic signed **checkpoints** cover the chain up to a point, so even a
deleted tail is detectable (the checkpoint proves the chain was longer).

Chains are **per campus** — each campus's chain is independent, so a
tamper in one tenant can never break another tenant's verification.

Honest guarantees (documented in detail in the module docs):
- the chain makes *modification*, *deletion* and *reordering* detectable
  by any verifier that can read the database;
- HMAC signatures prevent *forgery* of new entries without the server
  secret, but the secret lives on the server — a database administrator
  with both write access and the secret could re-sign;
- therefore this is **tamper-evident**, not absolute immutability;
- audit rows written before the chain was enabled are reported as
  *uncovered* (a coverage gap), never silently claimed as chained.
"""

from app.platform.cryptography.chain import (
    chain_hash,
    hmac_sign,
    payload_digest,
)
from app.platform.cryptography.models import (
    AuditChainCheckpoint,
    AuditChainEntry,
)
from app.platform.cryptography.repository import AuditChainRepository
from app.platform.cryptography.service import AuditChainService
from app.platform.cryptography.verifier import (
    ChainFinding,
    verify_chain,
)

__all__ = [
    "chain_hash",
    "hmac_sign",
    "payload_digest",
    "AuditChainCheckpoint",
    "AuditChainEntry",
    "AuditChainRepository",
    "AuditChainService",
    "ChainFinding",
    "verify_chain",
]
