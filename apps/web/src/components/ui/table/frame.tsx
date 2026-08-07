import {
  useCallback,
  useEffect,
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
}

// ---------------------------------------------------------------------------
// rows (FLIP + exit choreography, T33)
// ---------------------------------------------------------------------------

/** `fade-out-down` (motion fast 180ms) + buffer for the exit choreography. */
const EXIT_DURATION_MS = 240

function Cell<T>({ col, item, isCompact }: { col: Column<T>; item: T; isCompact: boolean }) {
  const align = resolveColumnAlign(col)
  const hasAlign = hasExplicitAlignment(col)
  return (
    <td
      className={cn(
        'px-5 text-sm text-[var(--color-text-primary)] whitespace-nowrap',
        hasAlign ? alignmentClass(align) : undefined,
        isCompact ? 'py-2.5' : 'py-3.5',
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
  isCompact,
  onRowClick,
  animateExit,
}: {
  items: T[]
  columns: Column<T>[]
  keyExtractor: (item: T) => string | number
  isCompact: boolean
  onRowClick?: (item: T) => void
  /** §6.4 T33 — rows that leave under a filter change fade out before removal. */
  animateExit?: boolean
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

  return (
    <tbody ref={containerRef} className="divide-y divide-[var(--color-divider)]">
      {items.map((item, idx) => (
        <tr
          key={keyExtractor(item)}
          ref={itemRef(keyExtractor(item))}
          className={cn(
            'motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)]',
            'animate-fade-in',
            onRowClick && 'cursor-pointer',
            'bg-[var(--color-surface)]',
            onRowClick && 'hover:bg-[var(--color-brand-accent-subtle)]',
            idx % 2 === 1 && 'bg-[var(--color-bg)]/40'
          )}
          style={{
            animationDelay: `${Math.min(idx * 20, 300)}ms`,
            animationFillMode: 'both',
          }}
          onClick={() => onRowClick?.(item)}
        >
          {columns.map((col) => (
            <Cell key={col.key} col={col} item={item} isCompact={isCompact} />
          ))}
        </tr>
      ))}
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
              <Cell key={col.key} col={col} item={item} isCompact={isCompact} />
            ))}
          </tr>
        ))}
    </tbody>
  )
}

// ---------------------------------------------------------------------------
// the frame
// ---------------------------------------------------------------------------

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
}: DataTableProps<T>) {
  // T23: Registry → comfortable; Ledger/Register → compact. Explicit wins.
  const isCompact = compact ?? (tableClass === 'ledger' || tableClass === 'register')

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

  const renderEmpty = (
    <div className="flex flex-col items-center justify-center py-16 text-center animate-fade-in">
      <div className="flex items-center justify-center h-12 w-12 rounded-2xl bg-[var(--color-bg)] mb-4">
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
  } else if (data.length === 0) {
    // legacy parity: the empty state sits bare, no overflow wrapper
    body = renderEmpty
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
            <tr className={cn(stickyHeader && 'sticky top-0 z-10')}>
              {columns.map((col) => {
                const align = resolveColumnAlign(col)
                // Untyped columns keep the legacy `text-left` position exactly;
                // typed columns use their declared alignment.
                const headerAlign = hasExplicitAlignment(col) ? alignmentClass(align) : 'text-left'
                const headerStyle: CSSProperties | undefined =
                  col.width !== undefined || col.minWidth !== undefined
                    ? { width: col.width, minWidth: col.minWidth }
                    : undefined
                return (
                  <th
                    key={col.key}
                    className={cn(
                      'px-5 py-3.5',
                      headerAlign,
                      'text-xs font-semibold text-[var(--color-text-tertiary)] uppercase tracking-wider bg-[var(--color-bg)]',
                      isCompact ? 'py-2.5 text-[10px]' : '',
                      col.hideOnMobile && 'hidden lg:table-cell',
                      col.className
                    )}
                    style={headerStyle}
                  >
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
                  </th>
                )
              })}
            </tr>
          </thead>
          <Rows
            items={displayed}
            columns={columns}
            keyExtractor={keyExtractor}
            isCompact={isCompact}
            onRowClick={onRowClick}
            animateExit={filterable}
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
        data={data}
        state={state}
        onStateChange={setState}
        viewKey={viewKey}
        placeholder={filterPlaceholder}
      />
      {body}
      {!loading && data.length > 0 && (
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
      )}
    </div>
  )
}
