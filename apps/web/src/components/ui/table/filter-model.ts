/**
 * SDMAS Table System v3 — filter model (§6 of TABLE_SYSTEM_V3.md).
 *
 * Pure, framework-free engine behind the smart filter rail:
 *
 *  - `FilterState` — query string + facet selections + range bounds.
 *  - typed predicates — which columns are searchable, facet- or range-
 *    filterable, derived from the column `type` (§3.1) with per-column
 *    overrides (`searchable`, `rangePresets`).
 *  - `applyFilters` — the single predicate engine used by the frame and
 *    by tests (T33: filtering is FLIP over this output, never a reload).
 *  - `parseQuery` — the discoverable query language (T32): `overdue`,
 *    `amount>5000`, `date>=2026-01-01`, `paid overdue` (AND), `paid OR
 *    overdue`, `name:"Exact phrase"`.
 *  - URL serialization (T34) — `f_q`, `f_<col>`, `f_<col>_min/_max`.
 *
 * Nothing here touches the DOM; the rail and frame own all effects.
 */

import type { Column } from './columns'
import { formatAmount, formatDateValue, formatNumber } from './columns'

// ---------------------------------------------------------------------------
// state
// ---------------------------------------------------------------------------

export interface RangeFilter {
  min?: number | string
  max?: number | string
}

export interface FilterState {
  /** Applied search / query-language text (debounced by the rail). */
  query: string
  /** colKey → selected facet values (exact string equality). */
  facets: Record<string, string[]>
  /** colKey → range bounds. Date columns hold `YYYY-MM-DD` strings. */
  ranges: Record<string, RangeFilter>
}

export function emptyFilterState(): FilterState {
  return { query: '', facets: {}, ranges: {} }
}

export function countActiveFilters(state: FilterState): number {
  let n = 0
  if (state.query) n += 1
  for (const values of Object.values(state.facets)) n += values.length
  for (const rng of Object.values(state.ranges)) {
    if (rng.min !== undefined || rng.max !== undefined) n += 1
  }
  return n
}

/** Deep equality — used for the saved-view dirty dot (T37). */
export function filtersEqual(a: FilterState, b: FilterState): boolean {
  if (a.query !== b.query) return false
  const ka = Object.keys(a.facets)
  const kb = Object.keys(b.facets)
  if (ka.length !== kb.length) return false
  for (const k of ka) {
    // order-insensitive: click order or URL order must not fake a dirty dot
    const va = new Set(a.facets[k] ?? [])
    const vb = new Set(b.facets[k] ?? [])
    if (va.size !== vb.size) return false
    for (const v of va) if (!vb.has(v)) return false
  }
  const ra = Object.keys(a.ranges)
  const rb = Object.keys(b.ranges)
  if (ra.length !== rb.length) return false
  for (const k of ra) {
    const x = a.ranges[k]
    const y = b.ranges[k]
    if (!x || !y) return false
    if (x.min !== y.min || x.max !== y.max) return false
  }
  return true
}

// ---------------------------------------------------------------------------
// typed column predicates (T27, T29, T31)
// ---------------------------------------------------------------------------

/** Raw cell value — the same access path the renderer uses. */
export function columnValue<T>(col: Column<T>, item: T): unknown {
  return col.accessor ? col.accessor(item) : (item as Record<string, unknown>)[col.key]
}

/** §3.1 types that participate in text search. Untyped columns behave like text. */
export function isSearchableColumn<T>(col: Column<T>): boolean {
  if (col.searchable !== undefined) return col.searchable
  if (!col.type) return true
  return col.type === 'text' || col.type === 'person' || col.type === 'relation' || col.type === 'numeric'
}

/** §3.1 `status` columns are facet-filtered (you filter them, not search them). */
export function isFacetColumn<T>(col: Column<T>): boolean {
  return col.type === 'status'
}

/** §3.1 numeric/amount/date/progress columns take range filters. */
export function isRangeColumn<T>(col: Column<T>): boolean {
  return (
    col.type === 'numeric' ||
    col.type === 'amount' ||
    col.type === 'date' ||
    col.type === 'progress'
  )
}

// ---------------------------------------------------------------------------
// facet counts (T29)
// ---------------------------------------------------------------------------

export interface FacetOption {
  value: string
  count: number
}

/**
 * Distinct values of a column with counts, ordered count-desc then alpha —
 * the at-a-glance list the facet panel shows. Pass rows already filtered by
 * every *other* active filter (the panel computes that; see the rail).
 */
export function facetCounts<T>(rows: readonly T[], col: Column<T>): FacetOption[] {
  const counts = new Map<string, number>()
  for (const row of rows) {
    const v = String(columnValue(col, row) ?? '')
    if (!v) continue
    counts.set(v, (counts.get(v) ?? 0) + 1)
  }
  return Array.from(counts.entries())
    .map(([value, count]) => ({ value, count }))
    .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value))
}

// ---------------------------------------------------------------------------
// the query language (T32)
// ---------------------------------------------------------------------------

export type RangeOp = '>' | '>=' | '<' | '<=' | '='

export type QueryTerm =
  | { kind: 'text'; needle: string; columnKey?: string }
  | { kind: 'facet'; columnKey: string; value: string }
  | { kind: 'range'; columnKey: string; op: RangeOp; value: number | string }

/**
 * Parse the query into OR-groups of AND-terms: `paid overdue` → [[paid,
 * overdue]], `paid OR overdue` → [[paid], [overdue]]. Bare words first
 * resolve against the facet vocabulary (from the current rows) so `overdue`
 * matches a status facet with its canonical casing; anything else is a
 * substring search across searchable columns.
 */
export function parseQuery<T>(query: string, rows: readonly T[], columns: Column<T>[]): QueryTerm[][] {
  if (!query.trim()) return []
  const vocab = facetVocabulary(rows, columns)
  return splitClauses(query)
    .map((tokens) => tokens.map((t) => parseTerm(t, columns, vocab)).filter((t): t is QueryTerm => t !== null))
    .filter((group) => group.length > 0)
}

function splitClauses(query: string): string[][] {
  return query
    .split(/\s+OR\s+/i)
    .map((clause) => tokenize(clause))
    .filter((t) => t.length > 0)
}

/** Whitespace split that respects `name:"Exact phrase"` quotes. */
function tokenize(clause: string): string[] {
  const out: string[] = []
  const re = /(?:[^\s:]+:"[^"]*")|[^\s]+/g
  let m: RegExpExecArray | null
  while ((m = re.exec(clause)) !== null) out.push(m[0])
  return out
}

function facetVocabulary<T>(rows: readonly T[], columns: Column<T>[]): Map<string, { columnKey: string; value: string }> {
  const map = new Map<string, { columnKey: string; value: string }>()
  for (const col of columns) {
    if (!isFacetColumn(col)) continue
    for (const row of rows) {
      const v = String(columnValue(col, row) ?? '').trim()
      if (!v) continue
      const key = v.toLowerCase()
      if (!map.has(key)) map.set(key, { columnKey: col.key, value: v })
    }
  }
  return map
}

function resolveColumn<T>(columns: Column<T>[], alias: string): Column<T> | undefined {
  const a = alias.toLowerCase()
  return (
    columns.find((c) => c.key.toLowerCase() === a) ??
    columns.find((c) => c.header.toLowerCase() === a)
  )
}

function parseTerm<T>(
  raw: string,
  columns: Column<T>[],
  vocab: Map<string, { columnKey: string; value: string }>
): QueryTerm | null {
  // range predicate: col op value  (amount>5000, date>=2026-01-01, amount=5000)
  // order matters: the two-char ops must be tried before their one-char peers
  const range = raw.match(/^([A-Za-z_][\w-]*)(>=|<=|=|>|<)(.+)$/)
  if (range) {
    const [, alias, op, rawValue] = range
    const col = resolveColumn(columns, alias)
    if (col && isRangeColumn(col)) {
      const value = parseRangeValue(col, rawValue)
      if (value !== undefined) return { kind: 'range', columnKey: col.key, op: op as RangeOp, value }
    }
  }

  // named column: col:value  (status:due, name:"Amina K")
  const named = raw.match(/^([A-Za-z_][\w-]*):(.*)$/)
  if (named) {
    const [, alias, rawValue] = named
    const col = resolveColumn(columns, alias)
    if (col) {
      const value = rawValue.replace(/^"(.*)"$/, '$1')
      if (isFacetColumn(col)) return { kind: 'facet', columnKey: col.key, value }
      if (isRangeColumn(col)) {
        const v = parseRangeValue(col, value)
        if (v !== undefined) return { kind: 'range', columnKey: col.key, op: '=', value: v }
      }
      return { kind: 'text', needle: value, columnKey: col.key }
    }
  }

  // bare word → facet value first (`overdue`, `paid`), then text search
  const facet = vocab.get(raw.trim().toLowerCase())
  if (facet) return { kind: 'facet', columnKey: facet.columnKey, value: facet.value }
  return { kind: 'text', needle: raw }
}

function parseRangeValue<T>(col: Column<T>, rawValue: string): number | string | undefined {
  const v = rawValue.trim()
  if (col.type === 'date') {
    // day-granular only — a time suffix would corrupt the boundary math
    if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return undefined
    return v
  }
  const n = Number(v)
  return Number.isFinite(n) ? n : undefined
}

export function matchesQuery<T>(row: T, groups: QueryTerm[][], columns: Column<T>[]): boolean {
  if (groups.length === 0) return true
  return groups.some((group) => group.every((term) => termMatches(row, term, columns)))
}

/**
 * §6.1 T27 — person cells may hold `{ name }` objects; search the name,
 * never `[object Object]`.
 */
export function searchTextOf(value: unknown): string {
  if (value == null) return ''
  if (typeof value === 'object' && 'name' in value) {
    return String((value as { name: unknown }).name ?? '')
  }
  return String(value)
}

function termMatches<T>(row: T, term: QueryTerm, columns: Column<T>[]): boolean {
  switch (term.kind) {
    case 'text': {
      const cols = term.columnKey
        ? columns.filter((c) => c.key === term.columnKey)
        : columns.filter(isSearchableColumn)
      const needle = term.needle.toLowerCase()
      return cols.some((c) => searchTextOf(columnValue(c, row)).toLowerCase().includes(needle))
    }
    case 'facet': {
      const col = columns.find((c) => c.key === term.columnKey)
      if (!col) return false
      return String(columnValue(col, row) ?? '').toLowerCase() === term.value.toLowerCase()
    }
    case 'range': {
      const col = columns.find((c) => c.key === term.columnKey)
      if (!col) return false
      const raw = columnValue(col, row)
      if (col.type === 'date') {
        const t = parseDateValue(raw)
        if (t === null) return false
        const boundary = String(term.value)
        if (term.op === '=') {
          const day = parseDateBoundary(boundary, false)
          return t >= day && t < day + 86_400_000
        }
        if (term.op === '>' || term.op === '>=') {
          const min = parseDateBoundary(boundary, false)
          return term.op === '>' ? t > min : t >= min
        }
        const max = parseDateBoundary(boundary, true)
        return term.op === '<' ? t < max : t <= max
      }
      const n = Number(raw)
      if (!Number.isFinite(n)) return false
      const v = Number(term.value)
      switch (term.op) {
        case '>':
          return n > v
        case '>=':
          return n >= v
        case '<':
          return n < v
        case '<=':
          return n <= v
        default:
          return n === v
      }
    }
  }
}

function parseDateValue(raw: unknown): number | null {
  if (raw == null || raw === '') return null
  const d = raw instanceof Date ? raw : new Date(String(raw))
  return Number.isNaN(d.getTime()) ? null : d.getTime()
}

/**
 * Date range bounds use `YYYY-MM-DD` day boundaries: a `min` is the start of
 * its day, a `max` the end of its day (so `date<=2026-01-02` includes the
 * whole of that day).
 */
function parseDateBoundary(value: string, isMax: boolean): number {
  const d = new Date(value + (isMax ? 'T23:59:59.999' : 'T00:00:00'))
  const t = d.getTime()
  return Number.isNaN(t) ? (isMax ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY) : t
}

// ---------------------------------------------------------------------------
// applyFilters — the single predicate engine (T33)
// ---------------------------------------------------------------------------

export function applyFilters<T>(rows: T[], state: FilterState, columns: Column<T>[]): T[] {
  const groups = parseQuery(state.query, rows, columns)
  return rows.filter((row) => {
    if (!matchesQuery(row, groups, columns)) return false
    for (const col of columns) {
      const selected = state.facets[col.key]
      if (selected && selected.length > 0) {
        const v = String(columnValue(col, row) ?? '')
        if (!selected.includes(v)) return false
      }
      const rng = state.ranges[col.key]
      if (rng && (rng.min !== undefined || rng.max !== undefined) && !inRange(col, row, rng)) return false
    }
    return true
  })
}

function inRange<T>(col: Column<T>, row: T, rng: RangeFilter): boolean {
  const raw = columnValue(col, row)
  if (col.type === 'date') {
    const t = parseDateValue(raw)
    if (t === null) return false
    if (rng.min !== undefined) {
      const min = parseDateBoundary(String(rng.min), false)
      if (t < min) return false
    }
    if (rng.max !== undefined) {
      const max = parseDateBoundary(String(rng.max), true)
      if (t > max) return false
    }
    return true
  }
  const n = Number(raw)
  if (!Number.isFinite(n)) return false
  if (rng.min !== undefined && n < Number(rng.min)) return false
  if (rng.max !== undefined && n > Number(rng.max)) return false
  return true
}

// ---------------------------------------------------------------------------
// immutable state helpers (used by the rail)
// ---------------------------------------------------------------------------

export function withFacet(state: FilterState, colKey: string, value: string, on: boolean): FilterState {
  const current = state.facets[colKey] ?? []
  const next = on
    ? Array.from(new Set([...current, value]))
    : current.filter((v) => v !== value)
  const facets = { ...state.facets }
  if (next.length) facets[colKey] = next
  else delete facets[colKey]
  return { ...state, facets }
}

export function withoutFacet(state: FilterState, colKey: string): FilterState {
  const facets = { ...state.facets }
  delete facets[colKey]
  return { ...state, facets }
}

export function withRange(state: FilterState, colKey: string, range: RangeFilter): FilterState {
  const ranges = { ...state.ranges }
  const next: RangeFilter = {}
  if (range.min !== undefined && range.min !== '') next.min = range.min
  if (range.max !== undefined && range.max !== '') next.max = range.max
  if (next.min !== undefined || next.max !== undefined) ranges[colKey] = next
  else delete ranges[colKey]
  return { ...state, ranges }
}

export function clearRange(state: FilterState, colKey: string): FilterState {
  const ranges = { ...state.ranges }
  delete ranges[colKey]
  return { ...state, ranges }
}

export function clearAllFilters(state: FilterState): FilterState {
  if (countActiveFilters(state) === 0) return state
  return { ...emptyFilterState() }
}

// ---------------------------------------------------------------------------
// URL serialization (T34)
// ---------------------------------------------------------------------------

/**
 * `?f_q=due&f_status=Due,Overdue&f_amount_min=5000` — the table's filters are
 * its own `f_`-prefixed params, so they coexist with page-level params.
 */
export function filtersToQueryString(state: FilterState): string {
  const p = new URLSearchParams()
  if (state.query) p.set('f_q', state.query)
  for (const [colKey, values] of Object.entries(state.facets)) {
    if (values.length > 0) p.set(`f_${colKey}`, values.join(','))
  }
  for (const [colKey, rng] of Object.entries(state.ranges)) {
    if (rng.min !== undefined) p.set(`f_${colKey}_min`, String(rng.min))
    if (rng.max !== undefined) p.set(`f_${colKey}_max`, String(rng.max))
  }
  return p.toString()
}

/** Inverse of `filtersToQueryString`; unknown/stale params are ignored. */
export function filtersFromQueryString<T>(search: string, columns: Column<T>[]): FilterState {
  const p = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search)
  const state = emptyFilterState()
  state.query = p.get('f_q') ?? ''
  for (const col of columns) {
    if (isFacetColumn(col)) {
      const raw = p.get(`f_${col.key}`)
      if (raw) state.facets[col.key] = raw.split(',').filter(Boolean)
    } else if (isRangeColumn(col)) {
      const min = p.get(`f_${col.key}_min`)
      const max = p.get(`f_${col.key}_max`)
      const rng: RangeFilter = {}
      if (min !== null) rng.min = col.type === 'date' ? min : Number(min)
      if (max !== null) rng.max = col.type === 'date' ? max : Number(max)
      if (rng.min !== undefined || rng.max !== undefined) state.ranges[col.key] = rng
    }
  }
  return state
}

// ---------------------------------------------------------------------------
// chip labels (T30)
// ---------------------------------------------------------------------------

/** `AMOUNT ≥ 5,000` / `DATE from 2026-01-01` — one chip per active range. */
export function rangeChipLabel<T>(col: Column<T>, rng: RangeFilter): string {
  const h = col.header.toUpperCase()
  const fmt = (v: number | string): string => {
    if (col.type === 'amount') return formatAmount(v, col.currency)
    if (col.type === 'date') return formatDateValue(v)
    if (col.type === 'progress') return `${v}${col.progressSuffix ?? '%'}`
    return formatNumber(v)
  }
  if (rng.min !== undefined && rng.max !== undefined) return `${h} ${fmt(rng.min)}–${fmt(rng.max)}`
  if (rng.min !== undefined) return `${h} ≥ ${fmt(rng.min)}`
  if (rng.max !== undefined) return `${h} ≤ ${fmt(rng.max)}`
  return h
}
