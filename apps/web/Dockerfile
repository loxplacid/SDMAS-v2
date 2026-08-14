# =============================================================
# SDMAS v2 — Frontend Dockerfile (multi-stage)
# =============================================================

# ---- Build Stage ----
FROM node:20-alpine AS builder

WORKDIR /build

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# ---- Nginx Runtime Stage ----
FROM nginx:1.27-alpine

# Base-layer hygiene: pull Alpine security fixes released since the base
# image tag was built (e.g. openssl <3.3.7-r0 CVE-2026-31789, zlib
# <1.3.2-r0 CVE-2026-22184, c-ares CVE-2026-33630).
RUN apk update && apk upgrade --no-cache

RUN addgroup -S sdmas && adduser -S sdmas -G sdmas

COPY --from=builder /build/dist /usr/share/nginx/html
COPY infrastructure/nginx/nginx.conf /etc/nginx/nginx.conf
COPY infrastructure/nginx/default.conf /etc/nginx/conf.d/default.conf

# Non-root nginx: bind an unprivileged port (8080) and keep the pid file in
# /tmp, which the sdmas user can write.  A non-root master cannot open
# /run/nginx.pid (image default) nor bind port 80.
RUN chown -R sdmas:sdmas /usr/share/nginx/html /var/cache/nginx /tmp && \
    chmod -R 755 /usr/share/nginx/html

USER sdmas

EXPOSE 8080

# 127.0.0.1 (not `localhost`): Alpine resolves localhost to ::1 first and
# nginx only listens on IPv4 — the IPv6 probe would spuriously fail.
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8080/health-check || exit 1
