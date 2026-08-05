# =============================================================
# SDMAS v2 — API Dockerfile (multi-stage)
# =============================================================

# ---- Builder Stage ----
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- Runtime Stage ----
FROM python:3.11-slim

RUN groupadd -r sdmas && useradd -r -g sdmas -d /app -s /sbin/nologin sdmas

WORKDIR /app

COPY --from=builder /root/.local /root/.local

ENV PATH=/root/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY alembic/ ./alembic/
COPY alembic.ini .
COPY app/ ./app/

RUN chown -R sdmas:sdmas /app

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
