# SDMAS v2 — Secrets & Environment Hygiene

This document is the operational playbook for keeping secrets out of the
repository. It was created after a verification audit found that the root
`.env` file had been committed to Git before the ignore rule existed.

## 1. Current state (after remediation)

* The root `.env` is **untracked** (`git rm --cached .env`). It still exists
  on disk for local development but is no longer in the index.
* `.gitignore` now ignores `.env` and every `.env.*` variant, while
  explicitly re-allowing tracked example files (`.env.example`).
* Only `.env.example` files are tracked: root, `apps/web/.env.example`,
  `apps/mobile/.env.example`. All contain safe placeholders.
* CI runs a **secret scan (gitleaks)** on every push/PR — see
  `.github/workflows/ci.yml` and `docs/CI.md`.

## 2. Rules

1. Never commit a real `.env`, `.env.local`, `.env.staging`, etc. The
   `.gitignore` handles this; gitleaks enforces it in CI.
2. Never put a real credential in a file that is tracked (examples,
   fixtures, docs). Use placeholders only.
3. `.env.example` is the canonical template. When you add a new setting to
   `app/config.py`, add its placeholder to `.env.example` in the same PR.
4. Prefer environment variables injected by the deployment (Docker
   `env_file`/secrets, orchestrator secrets) over checked-in files.
5. The API refuses to boot with the placeholder `JWT_SECRET` /
   `DOCUMENT_STORAGE_SECRET` when `ENVIRONMENT=production`.

## 3. Git history cleanup procedure (only if real credentials were committed)

The root `.env` was last modified by commit `62a72ab` (see
`git log --oneline -- .env`). **Before** rewriting history, determine
whether that commit ever contained real credentials:

1. Inspect the private working copy (do not share values):
   `git show 62a72ab:.env`
2. If **only placeholders** were ever committed, **no history rewrite is
   needed** — the untrack now done is sufficient.
3. If a real value was committed, purge history and rotate credentials:

   ```bash
   # 1. Untrack (done) and delete the working copy of the file
   git rm --cached .env
   # 2. Purge from all history using git-filter-repo (recommended)
   pip install git-filter-repo
   git filter-repo --invert-paths --path .env --force
   # 3. Force-push all branches/tags AFTER coordinated notification
   git push origin --force --all
   git push origin --force --tags
   # 4. Notify any clone holder to re-clone; expire old artifacts
   ```

   > `git-filter-repo` rewrites every commit hash. Coordinate with all
   > collaborators, then rotate credentials per the checklist below.
   > Alternative: `git filter-branch --index-filter 'git rm --cached --ignore-unmatch .env' -- --all`
   > (slower, but works without extra tooling).

4. GitHub-specific extras: enable secret scanning & push protection, purge
   the value from cached build artifacts / Actions logs, and check forks.

## 4. Credential rotation checklist (by type)

Rotate **all** of these if any real value ever lived in the committed
`.env`. Use each provider's own rotation tooling (new key → deploy → revoke
old key), never edit the old key in place.

| Credential type | Where used | Rotation action |
|---|---|---|
| LLM / LiteLLM / embedding API keys | `LLM_API_KEY`, `LITELLM_API_KEY`, `EMBEDDING_API_KEY` in `.env` | Revoke at the provider, issue a new key, update `.env`/deployment secrets |
| JWT secret | `JWT_SECRET` | Generate new: `openssl rand -hex 64`; all sessions invalidate on deploy |
| Document URL signing secret | `DOCUMENT_STORAGE_SECRET` | Generate new; existing signed URLs expire |
| Database passwords | `DATABASE_URL` credentials | Rotate at Postgres; update deployment secrets |
| SendGrid API key | `SENDGRID_API_KEY` | Rotate in SendGrid |
| Razorpay key id / secret / webhook secret | `RAZORPAY_*` | Rotate in Razorpay dashboard; webhook secret must be distinct from key secret |
| S3 credentials | `S3_*` | Rotate in the cloud provider IAM console |
| OAuth / IdP secrets | any `*_CLIENT_SECRET` | Rotate at the IdP |

After rotation: deploy, verify one happy-path + one failure-path request per
integration, then revoke the old value.

## 5. Developer quick start

```bash
cp .env.example .env      # then fill in real values for local services
```

`.env` is ignored by Git; you never need to stage it. If you are setting up
a new environment, copy the example and fill in placeholders only.
