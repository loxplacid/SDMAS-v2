/**
 * SDMAS Table System v3 — saved views (§6.5 of TABLE_SYSTEM_V3.md).
 *
 * A saved view captures the filter state plus, as the migration proceeds,
 * the column configuration (visibility/order/widths/pins), sort, density and
 * page size. Filters are the first field to exist, so the record is shaped
 * to grow: `filters` now, everything else optional.
 *
 * The collection stores the *applied* view id alongside the views so the
 * dirty dot (T37) survives menu open/close and page reloads — the menu's
 * local state alone would forget which view is active every time it mounts.
 *
 * Views are scoped per-page AND per-role by the caller's `viewKey` (T36):
 * the fee-due list for the accountant's role is a different `viewKey` than
 * the principal's.
 */

import type { FilterState } from './filter-model'

export interface SavedTableView {
  id: string
  name: string
  filters: FilterState
  /** Extension point: density arrives with the header migration. */
  density?: 'comfortable' | 'compact'
  createdAt: string
  updatedAt: string
}

export interface SavedViewCollection {
  views: SavedTableView[]
  appliedId: string | null
}

const PREFIX = 'sdmas:table-view:'

function keyFor(viewKey: string): string {
  return `${PREFIX}${viewKey}`
}

export function loadViews(viewKey: string): SavedViewCollection {
  try {
    const raw = localStorage.getItem(keyFor(viewKey))
    if (!raw) return { views: [], appliedId: null }
    const parsed: unknown = JSON.parse(raw)
    if (Array.isArray(parsed)) {
      // legacy array shape (pre-step-2) — no applied view
      return { views: parsed as SavedTableView[], appliedId: null }
    }
    if (parsed && typeof parsed === 'object') {
      const p = parsed as { views?: unknown; appliedId?: unknown }
      return {
        views: Array.isArray(p.views) ? (p.views as SavedTableView[]) : [],
        appliedId: typeof p.appliedId === 'string' ? p.appliedId : null,
      }
    }
    return { views: [], appliedId: null }
  } catch {
    return { views: [], appliedId: null }
  }
}

export function persistViews(
  viewKey: string,
  views: SavedTableView[],
  appliedId: string | null
): void {
  try {
    localStorage.setItem(keyFor(viewKey), JSON.stringify({ views, appliedId }))
  } catch {
    // storage unavailable (private mode, quota) — views live for the session
  }
}

export function uid(): string {
  const cryptoApi = globalThis.crypto
  if (cryptoApi && typeof cryptoApi.randomUUID === 'function') return cryptoApi.randomUUID()
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}
