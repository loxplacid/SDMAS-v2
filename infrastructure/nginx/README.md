# Nginx — security headers & Content-Security-Policy

## What was wrong (2026-08 hardening)

* **CSP was not actually enforced.**  `nginx.conf` declared the security
  headers (including `Content-Security-Policy`) at the **server** level,
  but every `location` that serves content (static assets, SPA) declared
  its own `add_header Cache-Control ...`.  Per nginx inheritance rules, a
  location that declares ANY `add_header` stops inheriting server-level
  `add_header` directives — so the CSP (and X-Frame-Options etc.) were
  silently dropped for exactly the responses that need them.
* **The web container had no config at all.**  `apps/web/Dockerfile`
  copies `infrastructure/nginx/default.conf` (build context
  `../../apps/web`), but the file did not exist — the web image could not
  build.
* The inline theme-init script in `index.html` forced `script-src
  'unsafe-inline'`; it is now an external file (`public/theme-init.js`).

## What we shipped

* `security-headers.conf` — shared snippet with the security headers and
  the enforced CSP; `include`d at the server level **and** inside every
  location that sets its own `add_header`.
* `default.conf` (web container) — SPA config carrying the same headers.
* CSP is **enforced** (not Report-Only) with `script-src 'self'` (no
  `'unsafe-inline'` for scripts).

## Unavoidable exceptions (documented)

| Directive | Why |
|---|---|
| `style-src 'unsafe-inline'` | React inline `style={{}}` attributes are used pervasively; removing them is a large front-end refactor. |
| `connect-src https://api.razorpay.com` | Razorpay payment checkout runs a third-party iframe/script. |
| `img-src data: blob:` | Inline icons and avatar blobs. |
| `upgrade-insecure-requests` | Production is HTTPS-only. |
| `worker-src 'self'` | PWA service worker (`sw.js`). |

## Tightening path (recommended follow-up)

1. Run in production for a release cycle; watch the browser console for
   CSP violations (the policy is enforced, so violations are either
   blocked functionality or acceptable).
2. If you want a reporting endpoint before tightening further, switch the
   `Content-Security-Policy` header to `Content-Security-Policy-Report-Only`
   temporarily and point `report-uri` at a collector.
3. Removing `style-src 'unsafe-inline'` requires converting React inline
   styles to CSS modules/classes — tracked separately.

## Verification

```bash
nginx -t -c /path/to/infrastructure/nginx/nginx.conf
curl -sI https://app.sdmas.example.com/ | grep -i content-security-policy
```
