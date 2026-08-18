# ADR-009 — No LLM/AI Dependency in the Migration Engine

Status: ACCEPTED · Date: 2026-08-16 (verified) · Decision: **Migration
auto-mapping is deterministic (normalized names, aliases, domain
dictionaries, confidence scores) with no LLM runtime dependency.**

## Context

- Enterprise data migration must work offline, deterministically, and
  explainably — an evaluator uploads a messy legacy export and gets
  reproducible mapping suggestions.
- LLM dependency would break determinism, add cost, and complicate tenant
  data handling.

## Decision

1. `discovery.py` profiles columns (`profile_columns`, type inference),
   suggests mappings (`suggest_mappings`) from normalized headers + alias
   dictionaries, and builds a default mapping with confidence scores.
2. Users correct mappings manually in the wizard; validation/preview/
   execute follow deterministically.
3. Similarity utilities (`app/intelligence/similarity`) are used where
   fuzzy matching adds value (data quality), never an external model.

## Consequences

- Mapping is reproducible and offline; the wizard flow is fully automated
  end-to-end (verified in `docs/enterprise/MIGRATION-VERIFICATION.md`).
- No AI/LLM packages in the dependency tree.

## Evidence

- `apps/api/app/domains/migration/discovery.py` (`suggest_mappings`,
  `build_default_mapping`, `detect_entities`), `transforms.py`,
  `validators.py`, `docs/enterprise/MIGRATION-VERIFICATION.md`,
  `docs/enterprise/SUPPLY-CHAIN-SECURITY-AUDIT.md`.
