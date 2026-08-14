# SDMAS v2 — Known Limitations & Risks

This document is the honest ledger of current gaps. It is updated as items
are resolved.

## Security / hygiene

1. **[RESOLVED] Root `.env` is tracked in git.** The `.gitignore` already
   excludes `.env`, and `git rm --cached .env` was applied (see
   docs/SECRETS.md). The file remains on disk for local development but is no
   longer in the index. Rotation of any secrets that ever lived in it is
   recommended.
2. **Root `node_modules/` was tracked** (4,474 files) — now untracked in the
   index but still present on disk. Safe to delete from the working tree
   (`rm -rf node_modules`); it is the archived v1 JS demo's dependency set.
3. **[RESOLVED] No CI/CD configuration exists in the repository.** CI
   workflows are wired up in `.github/workflows/ci.yml` and
   `.github/workflows/sbom_validation.yml` (see also docs/CI.md). The
   Makefile and `infrastructure/scripts/deploy.sh` support automated
   deployment.

## Billing / finance

4. **Billing cycle is not scheduled.** `SubscriptionService.process_period_end`
   and `expire_past_due` exist and are tested, but no cron/worker schedule
   invokes them yet — subscription invoices are only generated on demand.
5. **No UNIQUE constraint on `invoices(subscription_id, period_start)`** —
   double-invoicing is prevented by an application-level row lock, not by the
   schema. A migration would make it structural.
6. **`renew` from `past_due`** reactivates without inline payment
   verification — treat as an operator action, or gate on a paid invoice.
7. **Webhook `notes.campus_id` is trusted without an existence check** —
   safe today because notes are set server-side, but worth validating the
   campus resolves if notes ever become customer-editable.

## Data / migrations

8. **[RESOLVED] SQLite migration chain was broken before `034`** (a
   non-batch ALTER in `c09b48a8d73d`). The migration was repaired; the full
   chain `001 → 048` now applies cleanly from an empty SQLite database
   (verified). Production targets PostgreSQL.
9. **Legacy NULL-campus rows** (pre-tenancy data) are invisible to scoped
   tenant queries and exempted in a few legacy-data guards
   (`assert_tenant_scope_or_owner`, receipt/reconciliation campus checks).
   New data is always campus-tagged.
10. **Migration workspace (D2) exposes five entity types.** The engine
    supports multi-entity runs (`MigrationEngine.run_bulk`) with migrators
    for `users`, `students`, `academic`, `attendance`, and `fees` — the
    workspace wizard exposes all five via `get_registered_entity_types()`.
    Additional entity types can be added without changing the architecture.

## Reliability

10. **Two outbox tests were timing-flaky under full-suite load**
    (`tests/test_outbox/test_outbox.py` — reaper/stale-processing windows are
    wall-clock sensitive). They passed in isolation and in the full
    non-integration suite (1,652 tests) on 2026-08-14; the flakiness has not
    been reproduced recently but the wall-clock sensitivity remains.
11. **`process_period_end` idempotency relies on row locks** (see #5); under
    an extremely unlucky interleaving on non-Postgres dialects a duplicate
    invoice guard could degrade to the constraint-free path.
12. **The audit middleware skips requests faster than a minimum latency
    threshold** — extremely fast mutating requests can occasionally avoid
    audit capture (observed as a rare flake; not a data-integrity issue).

## Archive / legacy

13. **`_archive/legacy-v1/` and `_archive/backend/` are read-only
    historical artifacts.** They are not imported, tested, or deployed. They
    exist for reference and can be removed once the team is comfortable
    relying solely on git history.
