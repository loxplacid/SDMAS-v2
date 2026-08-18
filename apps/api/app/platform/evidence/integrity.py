"""Enterprise evidence — integrity core (pure functions).

Deterministic hashing primitives used by the evidence service:

- ``canonical_bytes`` — canonical JSON serialization (sorted keys, compact
  separators, UTF-8).  Same data → same bytes, regardless of key order or
  dict insertion order.
- ``sha256_hex`` — SHA-256 of bytes, hex-encoded (same algorithm family
  as the build-time ``scripts/evidence/`` tool).
- ``chain_hash`` — one link of the package hash chain:
  ``sha256(prev | target_type | target_id | digest)``.  Replaying the chain
  in order detects any change to a covered record.

All functions are pure — same input always yields the same output, which
is what makes verification deterministic.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_bytes(data: Any) -> bytes:
    """Canonical JSON serialization of ``data`` (sorted keys, compact)."""
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """SHA-256 hex digest of ``data``."""
    return hashlib.sha256(data).hexdigest()


def content_digest(*parts: Any) -> str:
    """SHA-256 over the canonical serialization of one or more values."""
    blob = b"".join(canonical_bytes(part) for part in parts)
    return sha256_hex(blob)


def chain_hash(prev_hash: str, target_type: str, target_id: int, digest: str) -> str:
    """One link of the evidence hash chain.

    ``prev_hash`` is the previous link's value (``""`` for the first entry
    in a package chain).  The link binds the previous state to this target
    and its digest, so any change to either breaks the chain.
    """
    return sha256_hex(f"{prev_hash}|{target_type}|{target_id}|{digest}".encode("utf-8"))


def verify_chain(
    *,
    prev_hash: str,
    target_type: str,
    target_id: int,
    digest: str,
    expected: str,
) -> bool:
    """Whether ``expected`` equals the recomputed chain link."""
    return chain_hash(prev_hash, target_type, target_id, digest) == expected
