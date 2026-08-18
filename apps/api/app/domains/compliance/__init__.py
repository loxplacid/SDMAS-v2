"""Declarative compliance engine (TASK 20).

A schema-driven, generic compliance framework that evaluates institutional
data against configurable regulation schemas.  No CBSE/ICSE/state rules are
hard-coded — the engine loads policy/schema packs at runtime.

Core concepts
-------------
- **Regulation** — a named regulation (e.g., "Affiliation Bylaws 2024")
- **Requirement** — a specific requirement within a regulation
- **Schema** — a validation schema pack defining rules for requirements
- **Rule** — a deterministic validation rule (condition + expected + severity)
- **Submission** — a batch of data submitted for compliance checking
- **Evidence** — supporting data attached to a submission
- **Approval** — human sign-off on a compliance result
- **Version** — schema versioning with effective dates

Connected domains
-----------------
Student data, academic data, finance, attendance, documents, evidence,
reports — the engine queries these via the session and evaluates rules
against their data.

Design principles
-----------------
- **Deterministic** — no AI narratives, no LLM calls
- **Explainable** — every evaluation records what rule fired, what data
  was checked, and why it passed/failed
- **Audit-first** — immutable evaluation records with full provenance
- **Schema-driven** — rules are defined in JSON, not in code
"""
