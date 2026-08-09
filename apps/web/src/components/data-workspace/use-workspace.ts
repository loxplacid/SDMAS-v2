import { useCallback, useEffect, useMemo, useState } from 'react'
import type { Column } from '../ui/table/columns'
import {
  countActiveFilters,
  emptyFilterState,
  filtersFromQueryString,
  filtersToQueryString,
  type FilterState,
} from '../ui/table/filter-model'
import type { SortRule } from '../ui/table'
import { sortFromQueryString, sortToQueryString } from '../../lib/workspace/sort'

/**
 * P8 — Data Workspace: workspace state with persistence.
 *
 * One hook owns everything a data module's workspace needs:
 *  - `filters` (FilterState) — the table's smart-filter model;
 *  - `sort` — multi-column rules;
 *  - `density` + column visibility — persisted per module (`viewKey`) in
 *    localStorage, so one module's preferences never leak into another;
 *  - `page`/`size` — server pagination;
 *  - `selection` — an id-set that survives pagination (bulk actions).
 *
 * Filters/sort/page are also synchronized with the URL (`f_*`, `sort`,
 * `page`), which restores the exact workspace when the user returns from a
 * detail page (P8 — detail continuity) and makes views shareable.
 */

export type WorkspaceDensity = 'comfortable' | 'compact' | 'dense'

export interface WorkspaceOptions<T> {
  /** Per-module (and per-role) scope for localStorage + URL params. */
  viewKey: string
  /** All available columns; visibility is a subset of this. */
  columns: Column<T>[]
  defaultPageSize?: number
  /** Mirror filters/sort/page to the URL. Default true. */
  urlSync?: boolean
}

const DENSITY_KEY = 'sdmas:ws-dens:'
const COLUMNS_KEY = 'sdmas:ws-col:'

function readStored<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    if (raw === null) return fallback
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

function parsePage(search: string): number {
  const n = Number(new URLSearchParams(search).get('page'))
  return Number.isInteger(n) && n > 0 ? n : 1
}

export interface UseWorkspaceResult<T> {
  /** The module scope (localStorage keys + URL params + saved views). */
  viewKey: string
  /** Smart-filter state (search + facets + ranges). */
  filters: FilterState
  onFiltersChange: (next: FilterState) => void
  hasActiveFilters: boolean
  /** Multi-column sort rules. */
  sort: SortRule[]
  onSortChange: (next: SortRule[]) => void
  /** Density — drives the table's compact prop. */
  density: WorkspaceDensity
  onDensityChange: (next: WorkspaceDensity) => void
  isCompact: boolean
  /** Column visibility. */
  visibleColumns: Column<T>[]
  visibleKeys: ReadonlySet<string>
  /** The visible keys in display order (P12 — column reorder). */
  visibleOrder: readonly string[]
  toggleColumn: (key: string) => void
  /** Move a visible column one position left (-1) or right (+1). */
  moveColumn: (key: string, dir: -1 | 1) => void
  /** Replace the visible set wholesale (saved-view restore). */
  setVisibleColumns: (keys: string[]) => void
  resetColumns: () => void
  /** Pagination. */
  page: number
  setPage: (next: number) => void
  size: number
  setSize: (next: number) => void
  /** Row selection (ids, stable across pages). */
  selection: Set<string | number>
  toggleRow: (key: string | number) => void
  selectPage: (keys: ReadonlyArray<string | number>) => void
  /** Replace the whole selection (the frame's header/row checkboxes). */
  replaceSelection: (next: Set<string | number>) => void
  clearSelection: () => void
  /** The active search query (kept current for page-level refetches). */
  query: string
}

export function useWorkspace<T>(options: WorkspaceOptions<T>): UseWorkspaceResult<T> {
  const { viewKey, columns, defaultPageSize = 20, urlSync = true } = options

  // ── URL-initialized state (restores the workspace on back-navigation) ──
  const [filters, setFilters] = useState<FilterState>(() =>
    urlSync ? filtersFromQueryString(window.location.search, columns) : emptyFilterState()
  )
  const [sort, setSort] = useState<SortRule[]>(() =>
    urlSync ? sortFromQueryString(new URLSearchParams(window.location.search).get('sort')) : []
  )
  const [page, setPageState] = useState<number>(() =>
    urlSync ? parsePage(window.location.search) : 1
  )
  const [size, setSize] = useState<number>(defaultPageSize)
  const [density, setDensity] = useState<WorkspaceDensity>(() =>
    readStored<WorkspaceDensity>(`${DENSITY_KEY}${viewKey}`, 'comfortable')
  )
  // Ordered visible keys: the array IS the display order (P12 — reorder),
  // the set is derived. Stored arrays from earlier versions load unchanged.
  const [visibleOrder, setVisibleOrder] = useState<string[]>(() => {
    const stored = readStored<string[]>(`${COLUMNS_KEY}${viewKey}`, [])
    const all = columns.map((c) => c.key)
    return stored.length > 0 ? stored.filter((k) => all.includes(k)) : [...all]
  })
  const visibleKeys = useMemo(() => new Set(visibleOrder), [visibleOrder])
  const [selection, setSelection] = useState<Set<string | number>>(new Set())

  // ── URL write-back (debounced; page/params coexist with other params) ──
  useEffect(() => {
    if (!urlSync) return
    const t = window.setTimeout(() => {
      const params = new URLSearchParams(window.location.search)
      for (const key of Array.from(params.keys())) {
        if (key.startsWith('f_') || key === 'sort' || key === 'page') params.delete(key)
      }
      for (const [k, v] of new URLSearchParams(filtersToQueryString(filters))) params.set(k, v)
      if (sort.length > 0) params.set('sort', sortToQueryString(sort))
      if (page > 1) params.set('page', String(page))
      const qs = params.toString()
      const url = qs ? `${window.location.pathname}?${qs}` : window.location.pathname
      window.history.replaceState(null, '', url)
    }, 180)
    return () => window.clearTimeout(t)
  }, [filters, sort, page, urlSync])

  // ── localStorage persistence (per module) ──
  useEffect(() => {
    try {
      localStorage.setItem(`${DENSITY_KEY}${viewKey}`, JSON.stringify(density))
    } catch { /* storage unavailable — preferences live for the session */ }
  }, [density, viewKey])

  useEffect(() => {
    try {
      localStorage.setItem(`${COLUMNS_KEY}${viewKey}`, JSON.stringify(visibleOrder))
    } catch { /* noop */ }
  }, [visibleOrder, viewKey])

  const visibleColumns = useMemo(() => {
    const byKey = new Map(columns.map((c) => [c.key, c] as const))
    const ordered: Column<T>[] = []
    for (const key of visibleOrder) {
      const col = byKey.get(key)
      if (col) ordered.push(col)
    }
    // internal columns (checkbox/expander) always render, trailing the
    // user-visible set (no host currently declares one mid-table)
    for (const col of columns) {
      if (col.key.startsWith('__')) ordered.push(col)
    }
    return ordered
  }, [columns, visibleOrder])

  const toggleColumn = useCallback((key: string) => {
    setVisibleOrder((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    )
  }, [])

  const moveColumn = useCallback((key: string, dir: -1 | 1) => {
    setVisibleOrder((prev) => {
      const idx = prev.indexOf(key)
      const target = idx + dir
      if (idx === -1 || target < 0 || target >= prev.length) return prev
      const next = [...prev]
      const [moved] = next.splice(idx, 1)
      next.splice(target, 0, moved)
      return next
    })
  }, [])

  const setVisibleColumns = useCallback(
    (keys: string[]) => {
      const all = new Set(columns.map((c) => c.key))
      setVisibleOrder(Array.from(new Set(keys)).filter((k) => all.has(k)))
    },
    [columns]
  )

  const resetColumns = useCallback(() => {
    setVisibleOrder(columns.map((c) => c.key))
  }, [columns])

  const setPage = useCallback((next: number) => setPageState(Math.max(1, next)), [])

  const toggleRow = useCallback((key: string | number) => {
    setSelection((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }, [])

  const selectPage = useCallback((keys: ReadonlyArray<string | number>) => {
    setSelection((prev) => {
      const next = new Set(prev)
      keys.forEach((k) => next.add(k))
      return next
    })
  }, [])

  const replaceSelection = useCallback((next: Set<string | number>) => setSelection(next), [])

  const clearSelection = useCallback(() => setSelection(new Set()), [])

  return {
    viewKey,
    filters,
    onFiltersChange: setFilters,
    hasActiveFilters: countActiveFilters(filters) > 0,
    sort,
    onSortChange: setSort,
    density,
    onDensityChange: setDensity,
    isCompact: density === 'compact',
    visibleColumns,
    visibleKeys,
    visibleOrder,
    toggleColumn,
    moveColumn,
    setVisibleColumns,
    resetColumns,
    page,
    setPage,
    size,
    setSize,
    selection,
    toggleRow,
    selectPage,
    replaceSelection,
    clearSelection,
    query: filters.query,
  }
}
