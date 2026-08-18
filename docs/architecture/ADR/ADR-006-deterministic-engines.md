# ADR-006 — Deterministic Engines over ML/AI

Status: ACCEPTED · Date: 2026-08-16 (verified) · Decision: **Risk,
intelligence, simulation, and optimization are deterministic and
explainable; no ML/AI/LLM runtime dependency.**

## Context

- The risk engine, intelligence detectors, migration auto-mapping, and the
  planned simulation/optimization engines must be reproducible,
  explainable, and auditable — same input always produces the same output.
- An LLM must not be a runtime dependency (cost, determinism, tenancy of
  data).

## Decision

1. **Risk** (`app/domains/risk/`) — rule-based evaluator with a fixed rule
   set (attendance/fees/academic/documents/admissions/operational),
   configurable thresholds; no stochastic terms.
2. **Intelligence** (`app/intelligence/`) — deterministic similarity
   (Jaro-Winkler, Jaccard), clustering (DBSCAN, label propagation, PageRank),
   and detector definitions; `data_quality` consumes the similarity module.
3. **Simulation** (`app/simulation/`) — pure affine/step forecast functions
   over frozen snapshots with a coefficient registry; golden tests pin exact
   outputs.
4. **Optimization** (`app/optimization/`) — CP-SAT with a fixed seed; golden
   tests assert exact objective values.
5. **Migration mapping** — deterministic column mapping via normalized names,
   aliases, and domain dictionaries with confidence scores (no LLM).

## Consequences

- Results are reproducible on any machine, for any tenant; golden tests are
  meaningful.
- No AI/LLM dependency in the dependency tree; audits are explainable.

## Evidence

- `app/domains/risk/rules.py`, `app/intelligence/*`,
  `docs/SIMULATION_ENGINE.md` §2, `docs/OPTIMIZATION_ENGINE.md` §2,
  `app/domains/migration/discovery.py` (`suggest_mappings`),
  `tests/test_simulation/`, `tests/test_optimization/`, `tests/test_risk/`.
