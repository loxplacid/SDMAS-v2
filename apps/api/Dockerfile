# =============================================================
# SDMAS v2 — API Dockerfile (multi-stage)
# =============================================================

# ---- Builder Stage ----
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
# --prefix (not --user): pip --user lands in /root/.local, and /root is
# 0700 root:root on Debian slim — no chown can grant the runtime user
# traversal through /root.  /opt/sdmas is world-readable by default, so
# the runtime user can import every package and run every console script.
# requirements.txt is generated from uv.lock (pinned + hashed), so
# --require-hashes makes every build install byte-identical wheels and
# rejects any package that lacks a recorded hash.
RUN pip install --no-cache-dir --require-hashes --prefix=/opt/sdmas -r requirements.txt

# ---- Runtime Stage ----
FROM python:3.11-slim

# Base-layer hygiene: apply any Debian security fixes released since the
# base image tag was built, and refresh the bundled build tooling (pip's
# setuptools/wheel ship CVEs that are fixed in newer lines — e.g.
# wheel <0.46.2 CVE-2026-24049, jaraco.context <6.1.0 CVE-2026-23949).
RUN apt-get update && apt-get upgrade -y --no-install-recommends && \
    pip install --no-cache-dir --upgrade setuptools wheel && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd -r sdmas && useradd -r -g sdmas -d /app -s /sbin/nologin sdmas

WORKDIR /app

COPY --from=builder /opt/sdmas /opt/sdmas

ENV PATH=/opt/sdmas/bin:$PATH \
    PYTHONPATH=/opt/sdmas/lib/python3.11/site-packages \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY alembic/ ./alembic/
COPY alembic.ini .
COPY app/ ./app/

# Shared storage mount point: compose mounts storage_data here so the API
# and worker share uploaded files (migration sources, document blobs).
# Pre-create with sdmas ownership so a fresh named volume inherits it
# (Docker copies image dir ownership into an empty volume) and the
# non-root runtime user can write inside it.
RUN mkdir -p /app/storage && chown -R sdmas:sdmas /app

USER sdmas

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Trusted-proxy handling is implemented in-app (app.core.security.client_ip)
# against the TRUSTED_PROXIES allowlist.  We deliberately do NOT pass
# --proxy-headers/--forwarded-allow-ips to uvicorn: ``*`` would trust
# X-Forwarded-For from any client, letting an attacker forge an IP and
# rotate the IP-keyed rate-limit/audit keys.  Without it, request.client.host
# stays the immediate peer (the nginx container) and the app decides whether
# to honour forwarded headers based on TRUSTED_PROXIES.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
