import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from 'react'
import { cn } from '../../../lib/utils'
import { AnimatedCount } from '../animated-count'
import { TableSkeleton } from '../skeleton'
import {
  alignmentClass,
  hasExplicitAlignment,
  renderCell,
  resolveColumnAlign,
  type Column,
} from './columns'
import { FilterRail } from './filter-rail'
import {
  applyFilters,
  clearAllFilters,
  countActiveFilters,
  emptyFilterState,
  filtersFromQueryString,
  filtersToQueryString,
  type FilterState,
} from './filter-model'
import { useFlipList } from '../../../lib/motion/flip'
import { useMotionTier } from '../../../lib/motion/use-motion-tier'

/**
 * SDMAS Table System v3 — the frame (§2 of TABLE_SYSTEM_V3.md).
 *
 * The instrument: sticky column band, hairline-divided body, zebra rows,
 * mount stagger, and the skeleton/empty states — all inside one component so
 * no page assembles a table by hand again.
 *
 * With `filterable` the frame gains the smart filter rail (§6): search +
 * facets + ranges + saved views, local filtering with FLIP (T33) and the
 * count footer. Without it, this frame renders byte-identical markup to the
 * legacy `Table` (see `legacy.tsx`) — the type system and rail are purely
 * additive.
 */

export type TableClass = 'registry' | 'ledger' | 'register'

/** P12 — three-tier density ladder (comfortable → compact → dense). */
export type TableDensity = 'comfortable' | 'compact' | 'dense'

/** Cell vertical padding per density tier. */
const CELL_PAD: Record<TableDensity, string> = {
  comfortable: 'py-3.5',
  compact: 'py-2.5',
  dense: 'py-1.5',
}

/** Header cell classes per density tier (height + type scale). */
const HEADER_PAD: Record<TableDensity, string> = {
  comfortable: 'py-3.5',
  compact: 'py-2.5 text-[10px]',
  dense: 'py-2 text-[10px]',
}

/**
 * One multi-column sort rule (P8 — Data Workspace). Columns sort by the
 * order the rules appear; the first rule is primary. Lives here so the
 * frame, the saved-view record and the workspace share one shape.
 */
export interface SortRule {
  key: string
  direction: 'asc' | 'desc'
}

export interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  keyExtractor: (item: T) => string | number
  /** Instrument class (§1.1). Drives the default density (T23). */
  class?: TableClass
  loading?: boolean
  emptyMessage?: string
  onRowClick?: (item: T) => void
  stickyHeader?: boolean
  /** Explicit density override; defaults follow the instrument class. */
  compact?: boolean
  /** P12 — three-tier density; wins over the legacy `compact` boolean. */
  density?: TableDensity
  className?: string
  /** §6 — enables the smart filter rail (local filtering + FLIP). */
  filterable?: boolean
  /** §6.5 — per-page + per-role key; enables the saved-view menu. */
  viewKey?: string
  /** §6.1 T26 — the table's own search hint. */
  filterPlaceholder?: string
  /** §6.4 T34 — reflect the filter state in the URL query string. */
  urlSync?: boolean
  /**
   * §6 — controlled mode for server-filtered pages: the frame does NOT
   * filter locally; changes are reported via `onFiltersChange`.
   */
  filters?: FilterState
  onFiltersChange?: (state: FilterState) => void
  /**
   * P8 — controlled multi-column sort. When supplied, sortable headers
   * become clickable: click sets the primary rule (asc → desc → remove),
   * Shift-click adds/toggles a secondary rule. The frame never sorts by
   * itself — the host owns `applySort` (local) or the server round-trip.
   */
  sort?: SortRule[]
  onSortChange?: (next: SortRule[]) => void
  /**
   * P8 — row selection. Adds a leading checkbox column; the header checkbox
   * selects the current page (server-paginated semantics, §12).
   */
  selectable?: boolean
  selectedKeys?: ReadonlySet<string | number>
  onSelectionChange?: (next: Set<string | number>) => void
  /**
   * P8 — roving keyboard navigation on rows: ↑/↓ move focus, Enter/Space
   * activate (row click, or selection when selectable).
   */
  keyboardNav?: boolean
  /**
   * P9 — the workspace's single "current" row (the inspector preview).
   * Highlighted distinctly from checkbox selection and marked `aria-current`.
   * Hosts keep this in sync with their URL-backed selection.
   */
  currentKey?: string | number
  /**
   * P9 — reports the row the roving keyboard navigation lands on (↑/↓), so a
   * workspace can follow keyboard focus with its inspector preview.
   */
  onActiveRowChange?: (item: T) => void
  /**
   * P8 — rows the filter rail computes facet counts from, when they differ
   * from the rendered page (local-mode workspaces paginate client-side and
   * must count against the full filtered set, not the page slice).
   */
  facetData?: T[]
  /**
   * P8 — replaces the frame's count footer entirely. Workspaces pass their
   * own footer so pagination ranges read "X–Y of Z" against the real total
   * (server totals, or the full client-side filtered set).
   */
  footer?: ReactNode
  /**
   * P8 — replaces the default empty-state block (workspaces differentiate
   * "no data exists" from "no results match your filters").
   */
  emptyContent?: ReactNode
  /** P8 — forwards a ref to the filter rail's search input (the `/` shortcut). */
  filterInputRef?: React.Ref<HTMLInputElement>
  /**
   * P12 — extra workspace state a saved view captures (multi-column sort +
   * visible column keys in display order). Optional; without it views keep
   * storing just the filter state. `columns` order is the display order.
   */
  viewSnapshot?: { sort?: SortRule[]; columns?: string[] }
  /** P12 — called when a saved view carrying sort/columns is applied. */
  onApplyViewSnapshot?: (snapshot: { sort?: SortRule[]; columns?: string[] }) => void
}

// ---------------------------------------------------------------------------
// rows (FLIP + exit choreography, T33)
// ---------------------------------------------------------------------------

/** `fade-out-down` (motion fast 180ms) + buffer for the exit choreography. */
const EXIT_DURATION_MS = 240

function Cell<T>({ col, item, density }: { col: Column<T>; item: T; density: TableDensity }) {
  const align = resolveColumnAlign(col)
  const hasAlign = hasExplicitAlignment(col)
  return (
    <td
      className={cn(
        'px-5 text-sm text-[var(--color-text-primary)] whitespace-nowrap',
        hasAlign ? alignmentClass(align) : undefined,
        CELL_PAD[density],
        col.hideOnMobile && 'hidden lg:table-cell',
        col.className
      )}
    >
      {renderCell(col, item)}
    </td>
  )
}

function Rows<T>({
  items,
  columns,
  keyExtractor,
  density,
  onRowClick,
  animateExit,
  selectable,
  selectedKeys,
  onToggleRow,
  keyboardNav,
  currentKey,
  onActiveRowChange,
}: {
  items: T[]
  columns: Column<T>[]
  keyExtractor: (item: T) => string | number
  density: TableDensity
  onRowClick?: (item: T) => void
  /** §6.4 T33 — rows that leave under a filter change fade out before removal. */
  animateExit?: boolean
  selectable?: boolean
  selectedKeys?: ReadonlySet<string | number>
  onToggleRow?: (key: string | number) => void
  keyboardNav?: boolean
  currentKey?: string | number
  onActiveRowChange?: (item: T) => void
}) {
  // FLIP: rows that survive a filter change keep position identity and
  // animate to their new place (tier-gated inside useFlipList).
  const { containerRef, itemRef } = useFlipList<T, HTMLTableSectionElement>(items, keyExtractor)

  // §8 gating: the exit choreography is a spatial move (fade + slide), so it
  // runs only in the precise tier. Efficient/minimal tiers snap — the same
  // gate the FLIP engine applies.
  const tier = useMotionTier()
  const animateExitPrecise = animateExit === true && tier === 'precise'

  const [exiting, setExiting] = useState<Array<{ key: string | number; item: T; idx: number }>>([])
  const prevRef = useRef<Map<string | number, { item: T; idx: number }>>(new Map())
  const timersRef = useRef<number[]>([])

  useEffect(() => {
    const next = new Map<string | number, { item: T; idx: number }>()
    items.forEach((item, idx) => next.set(keyExtractor(item), { item, idx }))

    if (animateExitPrecise) {
      const leaving = Array.from(prevRef.current.entries())
        .filter(([key]) => !next.has(key))
        .map(([key, rec]) => ({ key, ...rec }))
      if (leaving.length > 0) {
        setExiting((prev) => {
          const have = new Set(prev.map((x) => x.key))
          return [...prev, ...leaving.filter((x) => !have.has(x.key))]
        })
        // Per-batch timers: each removes only its own keys. Clearing a shared
        // timer here would orphan the previous batch's ghost rows forever
        // when filter changes overlap within the exit window.
        const keys = new Set(leaving.map((x) => x.key))
        const t = window.setTimeout(() => {
          timersRef.current = timersRef.current.filter((id) => id !== t)
          setExiting((prev) => prev.filter((x) => !keys.has(x.key)))
        }, EXIT_DURATION_MS)
        timersRef.current.push(t)
      }
    }
    prevRef.current = next
  }, [items, keyExtractor, animateExitPrecise])

  useEffect(
    () => () => {
      timersRef.current.forEach((t) => window.clearTimeout(t))
      timersRef.current = []
    },
    []
  )

  // P8 — roving keyboard navigation. ↓/↑ move focus between rows, Enter
  // triggers the row action, Space toggles selection when selectable.
  // True roving tabindex: only the last-focused row is tabbable (Tab moves
  // through the table as one stop, not every row).
  const [activeKey, setActiveKey] = useState<string | null>(null)
  const activeStillPresent =
    activeKey !== null && items.some((it) => String(keyExtractor(it)) === activeKey)
  const effectiveActive = activeStillPresent ? activeKey : null

  // P9 — item lookup for the keyboard-follow report (the roving nav moves
  // between DOM rows; the workspace needs the row's data).
  const keyToItem = useMemo(() => {
    const map = new Map<string, T>()
    items.forEach((it) => map.set(String(keyExtractor(it)), it))
    return map
  }, [items, keyExtractor])

  const handleRowKeyDown = (
    e: React.KeyboardEvent<HTMLTableRowElement>,
    item: T,
    key: string | number
  ) => {
    if (!keyboardNav) return
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      const rows = Array.from(
        e.currentTarget.parentElement?.querySelectorAll('tr[data-row-key]') ?? []
      )
      const idx = rows.indexOf(e.currentTarget)
      const next = rows[idx + (e.key === 'ArrowDown' ? 1 : -1)] as HTMLElement | undefined
      if (next) {
        const nextKey = next.getAttribute('data-row-key')
        if (nextKey !== null) {
          setActiveKey(nextKey)
          const nextItem = keyToItem.get(nextKey)
          if (nextItem !== undefined) onActiveRowChange?.(nextItem)
        }
        next.focus()
      }
    } else if (e.key === 'Enter') {
      e.preventDefault()
      onRowClick?.(item)
    } else if (e.key === ' ' && selectable) {
      e.preventDefault()
      onToggleRow?.(key)
    }
  }

  return (
    <tbody ref={containerRef} className="divide-y divide-[var(--color-divider)]">
      {items.map((item, idx) => {
        const key = keyExtractor(item)
        const selected = selectedKeys?.has(key) ?? false
        // P9 — the workspace's current row (inspector preview): a leading
        // accent rail + tint, visually distinct from checkbox selection.
        const isCurrent =
          currentKey !== undefined && String(currentKey) === String(key)
        return (
          <tr
            key={key}
            ref={itemRef(key)}
            data-row-key={keyboardNav ? String(key) : undefined}
            tabIndex={
              keyboardNav
                ? effectiveActive === null
                  ? idx === 0
                    ? 0
                    : -1
                  : effectiveActive === String(key)
                    ? 0
                    : -1
                : undefined
            }
            aria-selected={selectable ? selected : undefined}
            aria-current={isCurrent ? 'true' : undefined}
            onKeyDown={(e) => handleRowKeyDown(e, item, key)}
            className={cn(
              'motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)]',
              'animate-fade-in',
              onRowClick && 'cursor-pointer',
              'bg-[var(--color-surface)]',
              onRowClick && 'hover:bg-[var(--color-brand-accent-subtle)]',
              idx % 2 === 1 && 'bg-[var(--color-bg)]/40',
              (selected || isCurrent) && 'bg-[var(--color-brand-accent-subtle)]',
              keyboardNav && 'focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--color-brand-accent)]'
            )}
            style={{
              animationDelay: `${Math.min(idx * 20, 300)}ms`,
              animationFillMode: 'both',
              ...(isCurrent
                ? { boxShadow: 'inset 3px 0 0 0 var(--color-brand-accent)' }
                : {}),
            }}
            onClick={() => onRowClick?.(item)}
          >
            {selectable && (
              <td className={cn('px-2 text-center', CELL_PAD[density])}>
                <input
                  type="checkbox"
                  checked={selected}
                  onChange={() => onToggleRow?.(key)}
                  onClick={(e) => e.stopPropagation()}
                  aria-label={`Select row ${key}`}
                  className="h-3.5 w-3.5 accent-[var(--color-brand-accent)]"
                />
              </td>
            )}
            {columns.map((col) => (
              <Cell key={col.key} col={col} item={item} density={density} />
            ))}
          </tr>
        )
      })}
      {animateExitPrecise &&
        exiting.map(({ key, item, idx }) => (
          <tr
            key={`exit-${key}`}
            aria-hidden
            className={cn(
              'animate-fade-out-down',
              'bg-[var(--color-surface)]',
              idx % 2 === 1 && 'bg-[var(--color-bg)]/40'
            )}
            style={{ animationDuration: 'var(--motion-fast)', animationFillMode: 'both' }}
          >
            {columns.map((col) => (
              <Cell key={col.key} col={col} item={item} density={density} />
            ))}
          </tr>
        ))}
    </tbody>
  )
}

// ---------------------------------------------------------------------------
// the frame
// ---------------------------------------------------------------------------

/** P8 — header select-all checkbox with the tri-state (indeterminate) dot. */
function SelectAllCheckbox({
  checked,
  indeterminate,
  onToggle,
}: {
  checked: boolean
  indeterminate: boolean
  onToggle: () => void
}) {
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate
  }, [indeterminate])
  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checked}
      onChange={onToggle}
      aria-label="Select all rows on this page"
      className="h-3.5 w-3.5 accent-[var(--color-brand-accent)]"
    />
  )
}

export function DataTable<T>({
  columns,
  data,
  keyExtractor,
  class: tableClass,
  loading,
  emptyMessage = 'No data',
  onRowClick,
  stickyHeader = true,
  compact,
  className,
  filterable,
  viewKey,
  filterPlaceholder,
  urlSync,
  filters,
  onFiltersChange,
  sort,
  onSortChange,
  selectable,
  selectedKeys,
  onSelectionChange,
  keyboardNav,
  currentKey,
  onActiveRowChange,
  facetData,
  footer,
  emptyContent,
  filterInputRef,
  density,
  viewSnapshot,
  onApplyViewSnapshot,
}: DataTableProps<T>) {
  // T23: Registry → comfortable; Ledger/Register → compact. Explicit wins:
  // the P12 three-tier `density` over the legacy `compact` boolean over the
  // instrument-class default.
  const densityLevel: TableDensity =
    density ?? (compact ? 'compact' : tableClass === 'ledger' || tableClass === 'register' ? 'compact' : 'comfortable')

  const controlled = filters !== undefined
  const [internalState, setInternalState] = useState<FilterState>(() =>
    urlSync && !controlled ? filtersFromQueryString(window.location.search, columns) : emptyFilterState()
  )
  const state = controlled ? filters : internalState
  const setState = useCallback(
    (next: FilterState) => {
      if (controlled) onFiltersChange?.(next)
      else setInternalState(next)
    },
    [controlled, onFiltersChange]
  )

  // T34: the filter state is a shareable deep link (uncontrolled mode). The
  // table owns the `f_`-prefixed params; page-level params (term, page, …)
  // are merged in, never clobbered.
  useEffect(() => {
    if (!urlSync || controlled) return
    const t = window.setTimeout(() => {
      const params = new URLSearchParams(window.location.search)
      for (const key of Array.from(params.keys())) {
        if (key.startsWith('f_')) params.delete(key)
      }
      for (const [key, value] of new URLSearchParams(filtersToQueryString(state))) {
        params.set(key, value)
      }
      const qs = params.toString()
      const url = qs ? `${window.location.pathname}?${qs}` : window.location.pathname
      window.history.replaceState(null, '', url)
    }, 180)
    return () => window.clearTimeout(t)
  }, [state, urlSync, controlled])

  const displayed = filterable && !controlled ? applyFilters(data, state, columns) : data
  const active = filterable ? countActiveFilters(state) : 0

  // P8 — selection + sort are frame-level opt-ins. Sorting stays owned by the
  // host (local via applySort, or a server round-trip); the frame only renders.
  const sortableControlled = sort !== undefined && onSortChange !== undefined
  const handleSortClick = useCallback(
    (col: Column<T>, e: React.MouseEvent) => {
      if (!sortableControlled) return
      const current = sort ?? []
      const existing = current.find((r) => r.key === col.key)
      const multi = e.shiftKey
      if (!existing) {
        onSortChange(
          multi ? [...current, { key: col.key, direction: 'asc' as const }] : [{ key: col.key, direction: 'asc' as const }]
        )
      } else if (multi) {
        onSortChange(
          current.map((r) =>
            r.key === col.key ? { ...r, direction: r.direction === 'asc' ? 'desc' : 'asc' } : r
          )
        )
      } else if (existing.direction === 'asc') {
        onSortChange([{ key: col.key, direction: 'desc' as const }])
      } else {
        onSortChange([])
      }
    },
    [sort, onSortChange, sortableControlled]
  )

  const pageSelectedCount =
    selectable && !loading ? data.filter((item) => selectedKeys?.has(keyExtractor(item))).length : 0
  const pageAllSelected = pageSelectedCount > 0 && pageSelectedCount === data.length
  const pageSomeSelected = pageSelectedCount > 0 && pageSelectedCount < data.length
  const togglePageSelection = () => {
    if (!onSelectionChange || loading || data.length === 0) return
    const next = new Set(selectedKeys ?? [])
    if (pageAllSelected) {
      data.forEach((item) => next.delete(keyExtractor(item)))
    } else {
      data.forEach((item) => next.add(keyExtractor(item)))
    }
    onSelectionChange(next)
  }
  const toggleRowSelection = useCallback(
    (key: string | number) => {
      if (!onSelectionChange) return
      const next = new Set(selectedKeys ?? [])
      if (next.has(key)) next.delete(key)
      else next.add(key)
      onSelectionChange(next)
    },
    [selectedKeys, onSelectionChange]
  )

  const renderEmpty = (
    <div className="flex flex-col items-center justify-center py-16 text-center animate-fade-in">
      <div className="flex items-center justify-center h-12 w-12 rounded-xl bg-[var(--color-bg)] mb-4">
        <svg
          className="h-6 w-6 text-[var(--color-text-tertiary)]"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
          />
        </svg>
      </div>
      <p className="text-sm text-[var(--color-text-tertiary)]">{emptyMessage}</p>
    </div>
  )

  let body: ReactNode
  if (loading) {
    // legacy parity: the skeleton sits bare, no overflow wrapper
    body = (
      <div className="p-5">
        <TableSkeleton rows={5} cols={columns.length} />
      </div>
    )
  } else if (filterable && data.length === 0 && active > 0) {
    // P8 — controlled mode too: with active filters and an empty server
    // page, "no match" is the honest reading, not "no records yet".
    body = (
      <div className="flex flex-col items-center justify-center py-12 text-center animate-fade-in">
        <p className="text-sm text-[var(--color-text-secondary)]">
          No rows match the current filters.
        </p>
        <button
          type="button"
          onClick={() => setState(clearAllFilters(state))}
          className="mt-2 text-xs font-medium text-[var(--color-brand-accent)] hover:underline"
        >
          Clear filters
        </button>
      </div>
    )
  } else if (data.length === 0) {
    // legacy parity: the empty state sits bare, no overflow wrapper
    body = emptyContent ?? renderEmpty
  } else if (filterable && displayed.length === 0) {
    // §14: filtering never shows a skeleton — an honest "no match" state.
    body = (
      <div className="flex flex-col items-center justify-center py-12 text-center animate-fade-in">
        <p className="text-sm text-[var(--color-text-secondary)]">
          No rows match the current filters.
        </p>
        <button
          type="button"
          onClick={() => setState(clearAllFilters(state))}
          className="mt-2 text-xs font-medium text-[var(--color-brand-accent)] hover:underline"
        >
          Clear filters
        </button>
      </div>
    )
  } else {
    body = (
      <div className={cn('overflow-x-auto', className)}>
        <table className="min-w-full">
          <thead>
            <tr className={cn(stickyHeader && 'sticky top-0 z-[var(--z-sticky)]')}>
              {selectable && (
                <th
                  className={cn('px-2 text-center bg-[var(--color-bg)]', CELL_PAD[densityLevel])}
                >
                  <SelectAllCheckbox
                    checked={pageAllSelected}
                    indeterminate={pageSomeSelected}
                    onToggle={togglePageSelection}
                  />
                </th>
              )}
              {columns.map((col) => {
                const align = resolveColumnAlign(col)
                // Untyped columns keep the legacy `text-left` position exactly;
                // typed columns use their declared alignment.
                const headerAlign = hasExplicitAlignment(col) ? alignmentClass(align) : 'text-left'
                const headerStyle: CSSProperties | undefined =
                  col.width !== undefined || col.minWidth !== undefined
                    ? { width: col.width, minWidth: col.minWidth }
                    : undefined
                const ruleIndex = sort?.findIndex((r) => r.key === col.key) ?? -1
                const rule = ruleIndex >= 0 ? sort![ruleIndex] : undefined
                return (
                  <th
                    key={col.key}
                    aria-sort={rule ? (rule.direction === 'asc' ? 'ascending' : 'descending') : undefined}
                    className={cn(
                      'px-5',
                      HEADER_PAD[densityLevel],
                      headerAlign,
                      'text-xs font-semibold text-[var(--color-text-tertiary)] uppercase tracking-wider bg-[var(--color-bg)]',
                      col.hideOnMobile && 'hidden lg:table-cell',
                      col.className
                    )}
                    style={headerStyle}
                  >
                    {col.sortable && sortableControlled ? (
                      <button
                        type="button"
                        onClick={(e) => handleSortClick(col, e)}
                        className="group flex w-full items-center gap-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-brand-accent-ring)] rounded"
                        aria-label={`Sort by ${col.header}`}
                      >
                        {col.header}
                        {rule ? (
                          <>
                            <svg
                              className="h-3 w-3 text-[var(--color-brand-accent)]"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              {rule.direction === 'asc' ? (
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                              ) : (
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                              )}
                            </svg>
                            {sort!.length > 1 && (
                              <span className="text-[9px] font-bold tabular-nums text-[var(--color-brand-accent)]">
                                {ruleIndex + 1}
                              </span>
                            )}
                          </>
                        ) : (
                          <svg
                            className="h-3 w-3 text-[var(--color-text-muted)] opacity-0 group-hover:opacity-100 motion-safe:transition-opacity"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"
                            />
                          </svg>
                        )}
                      </button>
                    ) : (
                      <div className="flex items-center gap-1">
                        {col.header}
                        {col.sortable && (
                          <svg
                            className="h-3 w-3 text-[var(--color-text-tertiary)]"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"
                            />
                          </svg>
                        )}
                      </div>
                    )}
                  </th>
                )
              })}
            </tr>
          </thead>
          <Rows
            items={displayed}
            columns={columns}
            keyExtractor={keyExtractor}
            density={densityLevel}
            onRowClick={onRowClick}
            animateExit={filterable}
            selectable={selectable}
            selectedKeys={selectedKeys}
            onToggleRow={toggleRowSelection}
            keyboardNav={keyboardNav}
            currentKey={currentKey}
            onActiveRowChange={onActiveRowChange}
          />
        </table>
      </div>
    )
  }

  // legacy parity: non-filterable tables return the body exactly as the
  // legacy Table did (wrapper included only for the table itself).
  if (!filterable) return body

  return (
    <div className={cn('flex flex-col gap-3', className)}>
      <FilterRail
        columns={columns}
        data={facetData ?? data}
        state={state}
        onStateChange={setState}
        viewKey={viewKey}
        placeholder={filterPlaceholder}
        searchRef={filterInputRef}
        viewSnapshot={viewSnapshot}
        onApplyViewSnapshot={onApplyViewSnapshot}
      />
      {body}
      {!loading && data.length > 0 &&
        (footer ?? (
          <div className="flex items-center justify-between px-1 pb-1 text-xs text-[var(--color-text-tertiary)]">
            {/* T28: the count readout animates; the whole phrase stays one text
                node so it is reachable as a single string. */}
            <AnimatedCount
              value={displayed.length}
              duration={400}
              suffix={` of ${data.length.toLocaleString('en-US')} rows`}
              className="font-medium text-[var(--color-text-primary)]"
            />
            {active > 0 && (
              <button
                type="button"
                onClick={() => setState(clearAllFilters(state))}
                className="font-medium text-[var(--color-text-muted)] underline-offset-2 hover:text-[var(--color-text-primary)] hover:underline"
              >
                Clear all
              </button>
            )}
          </div>
        ))}
    </div>
  )
}
