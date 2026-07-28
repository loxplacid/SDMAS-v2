# SDMAS v2 — Migration Plan

## Purpose

This document describes the plan for migrating from the JavaScript SDMAS v1 implementation to the Python FastAPI SDMAS v2 backend.

## Current Status (Phase 1 — Foundation)

- The JavaScript implementation remains the **active behavioral reference** in the repository root.
- A Python FastAPI backend is being developed alongside it in `apps/api/`.
- Domain migration has **NOT** started yet.

## Migration Phases

| Phase | Scope | Status |
|-------|-------|--------|
| 0     | Architecture Reconciliation | Complete |
| 1     | Repository Scaffolding + Backend Foundation | **In progress** |
| 2     | Domain Migration (Student, Academic, Attendance, Fees) | Not started |
| 3     | Authentication & Authorization | Not started |
| 4     | AI & Analytics | Not started |
| 5     | Frontend | Not started |
| 6     | JS Archival + Cleanup | Not started |

## Rules

1. **DO NOT** delete or destructively modify existing JS files.
2. **DO NOT** rewrite existing JS behavior in Python during this phase.
3. **DO NOT** change existing JS tests.
4. **DO NOT** move JS into `legacy/` until Python behavioral parity is verified.
5. The Python backend is built alongside, not replacing, the JS implementation.

## Verification

Before archiving JS into `legacy/`, the Python backend must pass equivalent behavioral tests for all migrated functionality. This will be verified in Phase 6.

## Current Directories

- `apps/api/` — New Python FastAPI backend
- `backend/` — Earlier Python foundation (preserved for reference)
- Repository root — Active JS implementation