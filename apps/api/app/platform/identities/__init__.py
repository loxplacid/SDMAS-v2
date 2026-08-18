"""Canonical identity layer (platform).

One real-world person may be represented by several identifiers across SDMAS,
a legacy ERP, biometric/RFID systems, transport, and external organizations.
This package introduces a *canonical person* around existing entities
(Student/Teacher/Guardian are NOT replaced — they are referenced) plus the
external identities, aliases, deterministic matching, manual review, and
merge history needed to resolve a person to one canonical record.

All tables are tenant-scoped (``campus_id``) and every read goes through the
tenant-scoped repository, so identity data can never cross campus boundaries.
"""

from app.platform.identities.matching import (
    AUTO_CONFIRM_THRESHOLD,
    MANUAL_THRESHOLD,
    RULES,
    MatchProposal,
    MatchRule,
    match_persons,
    normalize_email,
    normalize_external_id,
    normalize_name,
    normalize_phone,
)
from app.platform.identities.models import (
    MATCH_STATUS_CONFIRMED,
    MATCH_STATUS_PENDING,
    MATCH_STATUS_REJECTED,
    MERGE_STATUS_COMPLETED,
    MERGE_STATUS_ROLLED_BACK,
    PERSON_STATUS_ACTIVE,
    PERSON_STATUS_ARCHIVED,
    PERSON_STATUS_MERGED,
    REFERENCED_ENTITY_TYPES,
    CanonicalPerson,
    ExternalIdentity,
    IdentityAlias,
    IdentityHistory,
    IdentityMatch,
    IdentityMerge,
)
from app.platform.identities.repository import IdentityRepository
from app.platform.identities.service import IdentityService

__all__ = [
    "AUTO_CONFIRM_THRESHOLD",
    "MANUAL_THRESHOLD",
    "MatchProposal",
    "MatchRule",
    "RULES",
    "match_persons",
    "normalize_email",
    "normalize_external_id",
    "normalize_name",
    "normalize_phone",
    "CanonicalPerson",
    "ExternalIdentity",
    "IdentityAlias",
    "IdentityHistory",
    "IdentityMatch",
    "IdentityMerge",
    "MATCH_STATUS_CONFIRMED",
    "MATCH_STATUS_PENDING",
    "MATCH_STATUS_REJECTED",
    "MERGE_STATUS_COMPLETED",
    "MERGE_STATUS_ROLLED_BACK",
    "PERSON_STATUS_ACTIVE",
    "PERSON_STATUS_ARCHIVED",
    "PERSON_STATUS_MERGED",
    "REFERENCED_ENTITY_TYPES",
    "IdentityRepository",
    "IdentityService",
]
