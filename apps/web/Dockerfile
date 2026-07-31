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

RUN addgroup -S sdmas && adduser -S sdmas -G sdmas

COPY --from=builder /build/dist /usr/share/nginx/html
COPY infrastructure/nginx/default.conf /etc/nginx/conf.d/default.conf

RUN chown -R sdmas:sdmas /usr/share/nginx/html /var/cache/nginx /var/run && \
    chmod -R 755 /usr/share/nginx/html

USER sdmas

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:80/health-check || exit 1
