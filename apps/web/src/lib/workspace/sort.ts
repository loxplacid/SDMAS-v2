/**
 * P8 — Data Workspace: the multi-column sort engine.
 *
 * Pure and deterministic — applies `SortRule[]` in rule order (first rule is
 * primary) over the table column type system, so amounts, dates, people and
 * statuses compare by their declared semantics rather than raw strings.
 * Null/empty values always sort last, in either direction.
 *
 * The frame never sorts by itself; the workspace applies this locally or
 * maps the rules to server params — one engine, two modes.
 */

import type { Column } from '../../components/ui/table/columns'
import { columnValue } from '../../components/ui/table/filter-model'
import type { SortRule } from '../../components/ui/table'

/** Raw comparable value of a cell, normalized for comparison. */
function comparableValue(value: unknown): { empty: boolean; value: number | string } {
  if (value == null || value === '') return { empty: true, value: '' }
  if (typeof value === 'object' && 'name' in value) {
    const name = String((value as { name: unknown }).name ?? '')
    return { empty: name === '', value: name.toLowerCase() }
  }
  if (typeof value === 'number') return { empty: false, value }
  const s = String(value)
  if (s === '') return { empty: true, value: '' }
  return { empty: false, value: s.toLowerCase() }
}

/** Order two non-empty comparable values by the column's declared semantics. */
function compareValues(a: number | string, b: number | string, col: Column<unknown>): number {
  if (col.type === 'numeric' || col.type === 'amount' || col.type === 'progress') {
    const na = Number(a)
    const nb = Number(b)
    if (Number.isFinite(na) && Number.isFinite(nb)) return na - nb
  }
  if (col.type === 'date') {
    const da = new Date(String(a ?? '')).getTime()
    const db = new Date(String(b ?? '')).getTime()
    if (Number.isFinite(da) && Number.isFinite(db)) return da - db
  }
  // text / person / relation / status: case-insensitive lexical
  return String(a).localeCompare(String(b), 'en')
}

/**
 * Sort rows by the given rules, applied in order. Null/empty cells always
 * sort LAST regardless of direction — the empty check happens outside the
 * direction negation, so descending never drags empties to the top.
 * When a column has no rule the sort is stable (Array.sort is stable).
 */
export function applySort<T>(rows: readonly T[], rules: readonly SortRule[], columns: Column<T>[]): T[] {
  if (!rules || rules.length === 0) return [...rows]
  const sorted = [...rows]
  sorted.sort((x, y) => {
    for (const rule of rules) {
      const col = columns.find((c) => c.key === rule.key)
      if (!col) continue
      const ca = comparableValue(columnValue(col, x))
      const cb = comparableValue(columnValue(col, y))
      if (ca.empty && cb.empty) continue
      if (ca.empty) return 1
      if (cb.empty) return -1
      const cmp = compareValues(ca.value, cb.value, col as Column<unknown>)
      if (cmp !== 0) return rule.direction === 'asc' ? cmp : -cmp
    }
    return 0
  })
  return sorted
}

/**
 * Cycle a sortable column's rule (the frame's header-click contract):
 *  - not sorted → becomes the primary rule ascending;
 *  - primary asc  → primary desc;
 *  - primary desc → removed;
 *  - `multi` (Shift-click) → added as a secondary rule ascending, or toggles
 *    an existing secondary's direction.
 */
export function cycleSort(rules: readonly SortRule[], key: string, multi = false): SortRule[] {
  const current = [...rules]
  const index = current.findIndex((r) => r.key === key)
  if (index === -1) {
    const rule: SortRule = { key, direction: 'asc' }
    return multi ? [...current, rule] : [rule]
  }
  const existing = current[index]
  if (multi && current.length > 1) {
    return current.map((r) =>
      r.key === key ? { ...r, direction: r.direction === 'asc' ? 'desc' : 'asc' } : r
    )
  }
  if (existing.direction === 'asc') {
    return [{ key, direction: 'desc' }]
  }
  return current.filter((r) => r.key !== key)
}

/** Serialize rules for the URL / saved views: `name:asc,class:desc`. */
export function sortToQueryString(rules: readonly SortRule[]): string {
  return rules.map((r) => `${r.key}:${r.direction}`).join(',')
}

/** Inverse of `sortToQueryString`; ignores malformed segments. */
export function sortFromQueryString(value: string | null): SortRule[] {
  if (!value) return []
  return value
    .split(',')
    .map((part) => {
      const m = part.match(/^(.+):(asc|desc)$/)
      if (!m) return null
      return { key: m[1], direction: m[2] as 'asc' | 'desc' }
    })
    .filter((r): r is SortRule => r !== null)
}
