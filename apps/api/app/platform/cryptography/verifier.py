"""Tamper-evident audit chain — pure verification core.

This module is the **independent verification mechanism**: it depends only
on the chain primitives (``chain.py``) and the rows passed to it — not on
the service, the API, or the write path.  Both the in-app verifier
(:class:`AuditChainService.verify`) and the standalone
``scripts/audit_verify.py`` call this same code, so the verifier never
shares state with the writer.

What is detected
----------------
- **modification** — an audit row whose content no longer matches its
  stored ``payload_hash`` (``PAYLOAD_MISMATCH``), or a chain entry whose
  ``current_hash`` was changed (``LINK_BROKEN``)
- **deletion** — a missing middle entry breaks prev-continuity
  (``PREV_MISMATCH`` / ``INDEX_GAP``); a deleted tail is caught by any
  checkpoint that covers it (``CHECKPOINT_TAIL_DELETION``); a deleted
  audit row referenced by a surviving chain entry is flagged
  (``MISSING_ENTRY_REF``)
- **reordering** — swapping entries breaks the prev→current link chain
  (entries are ordered by ``chain_index``; a swap changes which link each
  entry participates in, so recomputation fails)
- **forgery (with secret)** — HMAC signatures are verified when a secret
  is supplied; without it, integrity checks still run but forgery of new
  entries cannot be ruled out (reported as a limitation, not a break)

What is NOT claimed
-------------------
- Audit rows with no chain entry (written before the chain was enabled)
  are reported as ``UNCOVERED_AUDIT`` — a coverage gap, never silently
  treated as verified.
- If an attacker holds both database write access AND the server secret,
  they can re-sign the chain.  This mechanism is tamper-*evident*, not
  absolute immutability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from app.platform.cryptography.chain import (
    chain_hash,
    checkpoint_state_hash,
    hmac_sign,
    payload_digest,
)

#: Finding severities.
SEV_INFO = "info"
SEV_WARN = "warning"
SEV_CRIT = "critical"

#: Finding codes (stable — tests and the CLI rely on them).
F_PAYLOAD_MISMATCH = "PAYLOAD_MISMATCH"
F_LINK_BROKEN = "LINK_BROKEN"
F_PREV_MISMATCH = "PREV_MISMATCH"
F_INDEX_GAP = "INDEX_GAP"
F_MISSING_ENTRY_REF = "MISSING_ENTRY_REF"
F_UNCOVERED_AUDIT = "UNCOVERED_AUDIT"
F_CHECKPOINT_MISMATCH = "CHECKPOINT_MISMATCH"
F_CHECKPOINT_TAIL_DELETION = "CHECKPOINT_TAIL_DELETION"
F_SIGNATURE_INVALID = "SIGNATURE_INVALID"
F_CHECKPOINT_SIGNATURE_INVALID = "CHECKPOINT_SIGNATURE_INVALID"
F_ORDER_SWAP = "ORDER_SWAP"


@dataclass(frozen=True)
class ChainFinding:
    """One verification finding."""

    severity: str
    code: str
    message: str
    chain_index: Optional[int] = None


@dataclass
class ChainVerification:
    """The complete verification result for one campus chain."""

    campus_id: Optional[int]
    chain_ok: bool
    signatures_checked: bool
    entries: int
    checkpoints: int
    uncovered_audit_rows: int
    findings: list[ChainFinding] = field(default_factory=list)

    def has_findings(self, severity: str) -> bool:
        return any(f.severity == severity for f in self.findings)


def verify_chain(
    *,
    entries: Sequence[Any],
    checkpoints: Sequence[Any],
    audit_rows: Sequence[Any],
    campus_id: Optional[int] = None,
    secret: Optional[str] = None,
) -> ChainVerification:
    """Verify one campus's audit chain.

    Args:
        entries: ``AuditChainEntry`` rows ordered by ``chain_index``.
        checkpoints: ``AuditChainCheckpoint`` rows ordered by index.
        audit_rows: all ``AuditLog`` rows for the campus (chain-covered or
            not — uncovered rows are reported).
        campus_id: the chain key.
        secret: when supplied, HMAC signatures are verified.

    Returns:
        :class:`ChainVerification` with ``chain_ok`` = the chain is
        internally consistent (no critical finding).  Findings carry
        stable codes (see module constants).
    """
    findings: list[ChainFinding] = []
    entry_by_index: dict[int, Any] = {}
    entry_ids_seen: set[int] = set()

    # Contiguity + linkage.
    expected_index = 0
    prev_hash = ""
    ordered_entries: list[Any] = sorted(entries, key=lambda e: e.chain_index)
    for i, entry in enumerate(ordered_entries):
        if entry.id in entry_ids_seen:
            findings.append(
                ChainFinding(SEV_CRIT, F_ORDER_SWAP, f"duplicate entry id {entry.id}", i)
            )
        entry_ids_seen.add(entry.id)

        if entry.chain_index != expected_index:
            findings.append(
                ChainFinding(
                    SEV_CRIT,
                    F_INDEX_GAP,
                    f"chain index {entry.chain_index} expected {expected_index} "
                    f"(a middle entry was deleted?)",
                    entry.chain_index,
                )
            )
        entry_by_index[entry.chain_index] = entry

        if entry.prev_hash != prev_hash:
            findings.append(
                ChainFinding(
                    SEV_CRIT,
                    F_PREV_MISMATCH,
                    f"entry {entry.chain_index}: prev_hash does not match the "
                    f"previous entry's current hash (deletion or reordering?)",
                    entry.chain_index,
                )
            )

        recomputed = chain_hash(prev_hash, entry.payload_hash, campus_id, entry.chain_index)
        if recomputed != entry.current_hash:
            findings.append(
                ChainFinding(
                    SEV_CRIT,
                    F_LINK_BROKEN,
                    f"entry {entry.chain_index}: current_hash does not match "
                    f"the recomputed link (modification?)",
                    entry.chain_index,
                )
            )
        if secret is not None:
            expected_sig = hmac_sign(entry.current_hash, secret)
            if expected_sig != entry.signature:
                findings.append(
                    ChainFinding(
                        SEV_CRIT,
                        F_SIGNATURE_INVALID,
                        f"entry {entry.chain_index}: HMAC signature invalid",
                        entry.chain_index,
                    )
                )
        prev_hash = entry.current_hash
        expected_index += 1

    # Payload integrity: every entry's stored payload hash must match the
    # audit row it covers; a missing audit row is itself a finding.
    audit_by_id = {row.id: row for row in audit_rows}
    covered_audit_ids: set[int] = set()
    for entry in ordered_entries:
        covered_audit_ids.add(entry.audit_log_id)
        row = audit_by_id.get(entry.audit_log_id)
        if row is None:
            findings.append(
                ChainFinding(
                    SEV_CRIT,
                    F_MISSING_ENTRY_REF,
                    f"entry {entry.chain_index} references audit log "
                    f"{entry.audit_log_id} which no longer exists (deleted?)",
                    entry.chain_index,
                )
            )
            continue
        if payload_digest(row) != entry.payload_hash:
            findings.append(
                ChainFinding(
                    SEV_CRIT,
                    F_PAYLOAD_MISMATCH,
                    f"entry {entry.chain_index} covers audit log {row.id}: "
                    f"the event content no longer matches its stored hash "
                    f"(modified?)",
                    entry.chain_index,
                )
            )

    # Coverage gap: audit rows with no chain entry (written before the
    # chain was enabled) — honest limitation, not a chain break.
    uncovered = [row.id for row in audit_rows if row.id not in covered_audit_ids]

    # Checkpoints: recompute the state hash up to their coverage.
    current_hashes = [e.current_hash for e in ordered_entries]
    current_hashes_by_index = {e.chain_index: e.current_hash for e in ordered_entries}
    for cp in sorted(checkpoints, key=lambda c: c.up_to_chain_index):
        if cp.up_to_chain_index >= len(current_hashes):
            findings.append(
                ChainFinding(
                    SEV_CRIT,
                    F_CHECKPOINT_TAIL_DELETION,
                    f"checkpoint covers up to index {cp.up_to_chain_index} but "
                    f"the chain only has {len(current_hashes)} entries "
                    f"(tail deleted?)",
                    cp.up_to_chain_index,
                )
            )
            continue
        covered = [current_hashes_by_index[i] for i in range(cp.up_to_chain_index + 1)]
        recomputed_state = checkpoint_state_hash(covered)
        if recomputed_state != cp.state_hash:
            findings.append(
                ChainFinding(
                    SEV_CRIT,
                    F_CHECKPOINT_MISMATCH,
                    f"checkpoint up_to {cp.up_to_chain_index}: state hash does "
                    f"not match the recomputed chain",
                    cp.up_to_chain_index,
                )
            )
        if secret is not None:
            campus_label = "" if campus_id is None else str(campus_id)
            expected_sig = hmac_sign(
                f"{cp.state_hash}|{campus_label}|{cp.up_to_chain_index}",
                secret,
            )
            if expected_sig != cp.signature:
                findings.append(
                    ChainFinding(
                        SEV_CRIT,
                        F_CHECKPOINT_SIGNATURE_INVALID,
                        f"checkpoint up_to {cp.up_to_chain_index}: HMAC signature invalid",
                        cp.up_to_chain_index,
                    )
                )

    chain_ok = not any(f.severity == SEV_CRIT for f in findings)
    return ChainVerification(
        campus_id=campus_id,
        chain_ok=chain_ok,
        signatures_checked=secret is not None,
        entries=len(ordered_entries),
        checkpoints=len(checkpoints),
        uncovered_audit_rows=len(uncovered),
        findings=findings,
    )
