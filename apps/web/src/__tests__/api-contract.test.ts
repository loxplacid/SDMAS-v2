import { describe, it, expect } from 'vitest'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

/**
 * API routing contract guard (TASK 5 — API CONTRACT HARDENING).
 *
 * The frontend calls the backend with BOTH `/api/...` paths and bare legacy
 * prefixes (`/auth/login`, `/students`, `/attendance`, `/migration`,
 * `/admin/users`, `/classes/{id}/360`, `/teachers/{id}/360`).  Every bare
 * prefix must be routed to the API by:
 *
 *   1. the Vite dev proxy  (apps/web/vite.config.ts)
 *   2. the nginx dev conf  (infrastructure/nginx/dev.conf)
 *   3. the nginx prod conf  (infrastructure/nginx/nginx.conf)
 *
 * If any of these three falls out of sync, API requests get the SPA's
 * index.html instead of JSON — a silent, page-level breakage (the exact bug
 * this test was written for: Class 360 / Teacher 360 / admin user pages).
 *
 * The test is static (no HTTP): it parses the proxy/nginx configs and the
 * API client sources, and fails when a bare prefix is missing anywhere.
 */

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const webRoot = path.resolve(__dirname, '..', '..')
const repoRoot = path.resolve(webRoot, '..', '..')

const viteConfigPath = path.join(webRoot, 'vite.config.ts')
const devNginxPath = path.join(repoRoot, 'infrastructure', 'nginx', 'dev.conf')
const prodNginxPath = path.join(repoRoot, 'infrastructure', 'nginx', 'nginx.conf')
const apiDir = path.join(webRoot, 'src', 'api')

function readSource(p: string): string {
  return fs.readFileSync(p, 'utf-8')
}

/** Extract the proxy keys from vite.config.ts (e.g. `'/api': ...`). */
function viteProxyKeys(): string[] {
  const src = readSource(viteConfigPath)
  const match = src.match(/proxy:\s*\{([\s\S]*?)\n\s*\},/)
  if (!match) throw new Error('proxy block not found in vite.config.ts')
  const keys: string[] = []
  for (const line of match[1].split('\n')) {
    const m = line.match(/^\s*['"]([^'"]+)['"]\s*:/)
    if (m) keys.push(m[1])
  }
  return keys
}

/**
 * Extract the path prefixes nginx routes to the API.  Covers the explicit
 * `location /prefix/` blocks AND the content-negotiation regex
 * `location ~ ^/(a|b|c)(/|$)`.
 */
function nginxApiPrefixes(src: string): string[] {
  const prefixes = new Set<string>()
  // Explicit location blocks: `location /auth/ {` → /auth
  for (const m of src.matchAll(/location\s+\/([a-zA-Z0-9_-]+)\//g)) {
    prefixes.add('/' + m[1])
  }
  // Content-negotiation regex: `^/(students|teachers|attendance|...)(/|$)`
  for (const m of src.matchAll(/\^\s*\/\(([^)]+)\)/g)) {
    for (const part of m[1].split('|')) prefixes.add('/' + part)
  }
  return [...prefixes]
}

/**
 * Walk every file under src/api/ and collect the first path segment of every
 * API call.  Both `api.get<T>('/path'...)` string literals and template
 * literals (`/students/${id}`) are captured; `/api/...`-prefixed calls are
 * always proxied by the `/api` key and are therefore skipped.
 */
function frontendBarePrefixes(): string[] {
  const prefixes = new Set<string>()
  const files: string[] = []
  const walk = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) walk(full)
      else if (entry.name.endsWith('.ts') || entry.name.endsWith('.tsx')) files.push(full)
    }
  }
  walk(apiDir)

  for (const file of files) {
    const src = readSource(file)
    // `api.get<...>(`/path`...)`, `api.post(`...`)` — capture the first arg.
    for (const m of src.matchAll(/api\.(get|post|patch|put|delete)<[^>]*>\(\s*([`'"])([^`'"]*)/g)) {
      const arg = m[3]
      if (!arg.startsWith('/') || arg.startsWith('/api/')) continue
      const seg = '/' + arg.split('/').filter(Boolean)[0]
      prefixes.add(seg)
    }
    // Template literals with a static prefix, e.g. `/students/${id}`.
    for (const m of src.matchAll(/api\.(get|post|patch|put|delete)<[^>]*>\(\s*`(\/[^`$]*)\$\{/g)) {
      const prefix = '/' + m[2].split('/').filter(Boolean)[0]
      if (prefix.startsWith('/api/')) continue
      prefixes.add(prefix)
    }
  }
  return [...prefixes]
}

describe('API routing contract', () => {
  const barePrefixes = frontendBarePrefixes()
  const viteKeys = viteProxyKeys()
  const devNginx = nginxApiPrefixes(readSource(devNginxPath))
  const prodNginx = nginxApiPrefixes(readSource(prodNginxPath))

  it('finds at least the known bare prefixes (sanity check)', () => {
    expect(barePrefixes).toEqual(expect.arrayContaining(['/auth', '/students', '/attendance', '/migration', '/admin', '/classes', '/teachers']))
  })

  it('covers every bare frontend prefix in the Vite dev proxy', () => {
    const missing = barePrefixes.filter((p) => !viteKeys.includes(p))
    expect(missing).toEqual([])
  })

  it('covers every bare frontend prefix in the nginx dev config', () => {
    const missing = barePrefixes.filter((p) => !devNginx.includes(p))
    expect(missing).toEqual([])
  })

  it('covers every bare frontend prefix in the nginx production config', () => {
    const missing = barePrefixes.filter((p) => !prodNginx.includes(p))
    expect(missing).toEqual([])
  })
})
