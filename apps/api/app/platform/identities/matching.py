"""Deterministic identity matching rules (platform).

Rule-based, deterministic person matching — **no AI, no fuzzy libraries**.
Every rule compares *normalized* attributes and produces a fixed confidence
score.  The same input always yields the same proposal, so matching is
reproducible and auditable.

Confidence contract
-------------------
- ``>= AUTO_CONFIRM_THRESHOLD``  — the match is strong enough to confirm
  automatically (system actor).  Currently only ``name_dob`` (normalized
  full name + date of birth) and ``exact_external_id`` (same source system
  + external identifier) reach this bar.
- ``>= MANUAL_THRESHOLD``        — a plausible proposal that must be
  reviewed by a human (pending state).
- below ``MANUAL_THRESHOLD``     — not strong enough to propose; the rule
  reports no match.

All normalization is pure string manipulation (case folding, whitespace
collapsing, token sorting, digit extraction) so results never depend on
locale, randomness, or network access.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Optional

from app.platform.identities.models import (
    MATCH_STATUS_CONFIRMED,
    MATCH_STATUS_PENDING,
)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

#: Confidence at or above which a match is auto-confirmed (system actor).
AUTO_CONFIRM_THRESHOLD = 0.95
#: Confidence at or above which a match is proposed for manual review.
MANUAL_THRESHOLD = 0.6

# ---------------------------------------------------------------------------
# Normalization helpers (pure, deterministic)
# ---------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")
_DIGITS_RE = re.compile(r"\D+")


def _fold(value: str) -> str:
    """Case-fold + strip accents + collapse whitespace."""
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c))
    return _WS_RE.sub(" ", value).strip().lower()


def normalize_name(value: Optional[str]) -> str:
    """Normalized full name — folded, tokens sorted (order-insensitive)."""
    folded = _fold(value or "")
    if not folded:
        return ""
    tokens = sorted(folded.split())
    return " ".join(tokens)


def normalize_email(value: Optional[str]) -> str:
    """Normalized email — folded, whitespace stripped."""
    return _fold(value or "").replace(" ", "")


def normalize_phone(value: Optional[str]) -> str:
    """Normalized phone — digits only (country-code agnostic comparison)."""
    return _DIGITS_RE.sub("", value or "")


def normalize_external_id(value: Optional[str]) -> str:
    """Normalized external identifier — folded, spaces collapsed."""
    return _fold(value or "")


# ---------------------------------------------------------------------------
# Rule catalogue
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MatchRule:
    """A single deterministic matching rule."""

    rule_id: str
    confidence: float
    description: str
    #: True when the rule may auto-confirm (>= AUTO_CONFIRM_THRESHOLD).
    auto_confirmable: bool = False


RULES: dict[str, MatchRule] = {
    rule.rule_id: rule
    for rule in (
        MatchRule(
            "exact_external_id",
            0.99,
            "Same source system + external identifier",
            auto_confirmable=True,
        ),
        MatchRule(
            "name_dob",
            0.97,
            "Normalized full name + date of birth",
            auto_confirmable=True,
        ),
        MatchRule(
            "name_email",
            0.88,
            "Normalized full name + email",
        ),
        MatchRule(
            "name_phone",
            0.82,
            "Normalized full name + phone",
        ),
        MatchRule(
            "email_phone",
            0.75,
            "Email + phone",
        ),
        MatchRule(
            "exact_email",
            0.7,
            "Normalized email",
        ),
        MatchRule(
            "exact_phone",
            0.65,
            "Normalized phone",
        ),
    )
}


@dataclass
class MatchProposal:
    """A deterministic match proposal between two candidate persons."""

    matched_by: str
    confidence: float
    evidence: dict[str, Any] = field(default_factory=dict)
    #: True when confidence clears the auto-confirm bar.
    auto_confirm: bool = False

    @property
    def status(self) -> str:
        """Manual review state derived from confidence.

        ``confirmed`` when the rule is auto-confirmable and the confidence
        clears the auto-confirm threshold; ``pending`` otherwise (a human
        must review).
        """
        if self.auto_confirm:
            return MATCH_STATUS_CONFIRMED
        return MATCH_STATUS_PENDING


def match_persons(
    a: dict[str, Any],
    b: dict[str, Any],
) -> Optional[MatchProposal]:
    """Deterministically match two persons by their best-known attributes.

    ``a`` / ``b`` are dicts with any of the keys: ``first_name``,
    ``last_name``, ``date_of_birth`` (ISO date string or ``date``),
    ``email``, ``phone``, ``source_system``, ``external_id``.

    Returns the strongest proposal with confidence >= ``MANUAL_THRESHOLD``,
    or ``None`` when no rule fires strongly enough.  Rules are evaluated in
    a fixed order (most specific first); the first rule that fires wins so
    the result is deterministic.
    """
    name_a = normalize_name(_full_name(a))
    name_b = normalize_name(_full_name(b))
    dob_a = _iso_date(a.get("date_of_birth"))
    dob_b = _iso_date(b.get("date_of_birth"))
    email_a = normalize_email(a.get("email"))
    email_b = normalize_email(b.get("email"))
    phone_a = normalize_phone(a.get("phone"))
    phone_b = normalize_phone(b.get("phone"))

    # exact external identifier — strongest signal, only when both sides
    # name the same source system.
    src_a = _fold(a.get("source_system") or "")
    src_b = _fold(b.get("source_system") or "")
    ext_a = normalize_external_id(a.get("external_id"))
    ext_b = normalize_external_id(b.get("external_id"))
    if src_a and src_b and src_a == src_b and ext_a and ext_a == ext_b:
        rule = RULES["exact_external_id"]
        return MatchProposal(
            matched_by=rule.rule_id,
            confidence=rule.confidence,
            evidence={
                "source_system": src_a,
                "external_id": ext_a,
                "name_a": name_a,
                "name_b": name_b,
            },
            auto_confirm=rule.auto_confirmable,
        )

    # normalized full name + date of birth — the classic identity pair.
    if name_a and name_b and name_a == name_b and dob_a and dob_a == dob_b:
        rule = RULES["name_dob"]
        return MatchProposal(
            matched_by=rule.rule_id,
            confidence=rule.confidence,
            evidence={
                "name": name_a,
                "date_of_birth": dob_a,
                "email_a": email_a,
                "email_b": email_b,
            },
            auto_confirm=rule.auto_confirmable,
        )

    name_equal = bool(name_a and name_b and name_a == name_b)
    email_equal = bool(email_a and email_b and email_a == email_b)
    phone_equal = bool(phone_a and phone_b and phone_a == phone_b)

    if name_equal and email_equal:
        rule = RULES["name_email"]
    elif name_equal and phone_equal:
        rule = RULES["name_phone"]
    elif email_equal and phone_equal:
        rule = RULES["email_phone"]
    elif email_equal:
        rule = RULES["exact_email"]
    elif phone_equal:
        rule = RULES["exact_phone"]
    else:
        return None

    evidence: dict[str, Any] = {}
    if name_equal:
        evidence["name"] = name_a
    if email_equal:
        evidence["email"] = email_a
    if phone_equal:
        evidence["phone"] = phone_a
    return MatchProposal(
        matched_by=rule.rule_id,
        confidence=rule.confidence,
        evidence=evidence,
        auto_confirm=rule.auto_confirmable,
    )


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _full_name(person: dict[str, Any]) -> str:
    first = person.get("first_name") or ""
    last = person.get("last_name") or ""
    return f"{first} {last}".strip()


def _iso_date(value: Any) -> str:
    """Return an ISO date string for a date/datetime/str, or ``""``."""
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    return str(value).strip()[:10]
