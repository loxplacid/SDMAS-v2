/**
 * SDMAS Table System v3 — the filter rail (§6 of TABLE_SYSTEM_V3.md).
 *
 * The single entry point for finding rows (T26–T37):
 *
 *  - one search box, 320→480px on focus, debounced 180ms (T26–T28);
 *  - a discoverable query-language suggestion card (T32);
 *  - facet chips — the *only* persistent filter affordance (T30);
 *  - the filter panel: per-column facet lists with counts (T29) and
 *    range inputs with domain-authored presets (T31);
 *  - the saved-view menu (T35–T37) when the host supplies a `viewKey`.
 *
 * The component is controlled (`state` + `onStateChange`); the frame owns
 * URL sync and local filtering. Facet counts are computed from the rows the
 * host passes — for server-filtered pages that is the current page's rows,
 * an approximation the host accepts by choosing controlled mode.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from 'react'
import { cn } from '../../../lib/utils'
import { SearchInput } from '../search-input'
import type { Column } from './columns'
import {
  applyFilters,
  clearAllFilters,
  clearRange,
  countActiveFilters,
  facetCounts,
  filtersEqual,
  isFacetColumn,
  isRangeColumn,
  rangeChipLabel,
  withFacet,
  withRange,
  withoutFacet,
  type FilterState,
  type RangeFilter,
} from './filter-model'
import {
  loadViews,
  persistViews,
  uid,
  type SavedTableView,
  type SavedViewCollection,
} from './saved-views'

export interface FilterRailProps<T> {
  columns: Column<T>[]
  /** Full row set — used for facet counts and the query vocabulary. */
  data: T[]
  state: FilterState
  onStateChange: (next: FilterState) => void
  /** Per-page + per-role storage key; enables the saved-view menu (T36). */
  viewKey?: string
  /** Search-box hint (T26) — the table's own, never a bare "Search". */
  placeholder?: string
  /** P8 — forwarded to the search input (the `/` shortcut focuses it). */
  searchRef?: React.Ref<HTMLInputElement>
  className?: string
}

// ---------------------------------------------------------------------------
// small primitives
// ---------------------------------------------------------------------------

function RailButton({
  children,
  active = false,
  'aria-label': ariaLabel,
}: {
  children: ReactNode
  active?: boolean
  'aria-label'?: string
}) {
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      className={cn(
        'inline-flex h-8 shrink-0 items-center gap-1.5 rounded-[10px] border px-2.5 text-xs font-medium',
        'border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-secondary)]',
        'motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)]',
        'hover:border-[var(--color-border-hover)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)]',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-brand-accent-ring)]',
        active &&
          'border-[var(--color-brand-accent)] bg-[var(--color-brand-accent-subtle)] text-[var(--color-brand-accent)]'
      )}
    >
      {children}
    </button>
  )
}

/** §6.2 T30 — the only persistent filter affordance. */
function Chip({
  label,
  onRemove,
  children,
}: {
  label: string
  onRemove: () => void
  children: ReactNode
}) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-[var(--color-border)] bg-[var(--color-bg)] py-0.5 pl-2 pr-0.5 text-xs text-[var(--color-text-secondary)]">
      {children}
      <button
        type="button"
        aria-label={`Remove ${label}`}
        onClick={onRemove}
        className="flex h-4 w-4 items-center justify-center rounded-full text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)]"
      >
        <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </span>
  )
}

/** Popover with outside-click + Escape handling (same contract as DropdownMenu). */
function RailPopover({
  trigger,
  align = 'right',
  className,
  children,
}: {
  trigger: ReactNode
  align?: 'left' | 'right'
  className?: string
  children: ReactNode | ((close: () => void) => ReactNode)
}) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const close = useCallback(() => setOpen(false), [])

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) close()
    }
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape') close()
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open, close])

  return (
    <div ref={rootRef} className="relative shrink-0">
      <div onClick={() => setOpen((o) => !o)}>{trigger}</div>
      {open && (
        <div
          className={cn(
            'absolute z-[var(--z-dropdown)] mt-1.5 animate-fade-in-scale rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-xl',
            align === 'right' ? 'right-0' : 'left-0',
            className
          )}
        >
          {typeof children === 'function' ? children(close) : children}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// the filter panel (T29 facet lists, T31 range inputs + presets)
// ---------------------------------------------------------------------------

function FilterPanel<T>({
  columns,
  data,
  state,
  onStateChange,
}: {
  columns: Column<T>[]
  data: T[]
  state: FilterState
  onStateChange: (next: FilterState) => void
}) {
  const facetCols = columns.filter(isFacetColumn)
  const rangeCols = columns.filter(isRangeColumn)

  if (facetCols.length === 0 && rangeCols.length === 0) {
    return (
      <div className="w-64 p-3 text-sm text-[var(--color-text-muted)]">No filterable columns.</div>
    )
  }

  return (
    <div
      role="dialog"
      aria-label="Filter panel"
      className="flex max-h-[26rem] w-[19rem] flex-col overflow-y-auto p-2"
    >
      {facetCols.map((col) => {
        // T29: counts reflect the OTHER active filters, never this column's own.
        const base = applyFilters(data, withoutFacet(state, col.key), columns)
        const options = facetCounts(base, col)
        const selected = state.facets[col.key] ?? []
        return (
          <section key={col.key} className="mb-2">
            <div className="flex items-center justify-between px-2 py-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">
                {col.header}
              </span>
              {selected.length > 0 && (
                <button
                  type="button"
                  onClick={() => onStateChange(withoutFacet(state, col.key))}
                  className="text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]"
                >
                  Clear
                </button>
              )}
            </div>
            <div className="max-h-40 overflow-y-auto">
              {options.map(({ value, count }) => (
                <label
                  key={value}
                  className="flex cursor-pointer items-center justify-between gap-2 rounded-md px-2 py-1 text-sm hover:bg-[var(--color-surface-hover)]"
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <input
                      type="checkbox"
                      checked={selected.includes(value)}
                      onChange={() =>
                        onStateChange(withFacet(state, col.key, value, !selected.includes(value)))
                      }
                      className="h-3.5 w-3.5 accent-[var(--color-brand-accent)]"
                    />
                    <span className="truncate">{value}</span>
                  </span>
                  <span className="text-xs tabular-nums text-[var(--color-text-muted)]">{count}</span>
                </label>
              ))}
              {options.length === 0 && (
                <p className="px-2 py-1 text-xs text-[var(--color-text-muted)]">No values.</p>
              )}
            </div>
          </section>
        )
      })}

      {rangeCols.map((col) => {
        const rng = state.ranges[col.key] ?? {}
        const isDate = col.type === 'date'
        const boundValue = (v: string | number | undefined) => (v === undefined ? '' : String(v))
        const setBound = (bound: 'min' | 'max', raw: string) => {
          const value = raw === '' ? undefined : isDate ? raw : Number(raw)
          onStateChange(withRange(state, col.key, { ...rng, [bound]: value }))
        }
        return (
          <section
            key={col.key}
            className="mb-2 border-t border-[var(--color-divider)] pt-2 first:border-t-0 first:pt-0"
          >
            <div className="flex items-center justify-between px-2 py-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">
                {col.header}
              </span>
              {(rng.min !== undefined || rng.max !== undefined) && (
                <button
                  type="button"
                  onClick={() => onStateChange(clearRange(state, col.key))}
                  className="text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]"
                >
                  Clear
                </button>
              )}
            </div>
            <div className="flex items-center gap-1.5 px-2 pb-1">
              <input
                type={isDate ? 'date' : 'number'}
                value={boundValue(rng.min)}
                onChange={(e) => setBound('min', e.target.value)}
                placeholder={isDate ? 'From' : 'Min'}
                aria-label={`${col.header} minimum`}
                className="h-7 w-full min-w-0 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-xs text-[var(--color-text-primary)] focus-visible:border-[var(--color-brand-accent)] focus-visible:outline-none"
              />
              <span className="text-[var(--color-text-muted)]">–</span>
              <input
                type={isDate ? 'date' : 'number'}
                value={boundValue(rng.max)}
                onChange={(e) => setBound('max', e.target.value)}
                placeholder={isDate ? 'To' : 'Max'}
                aria-label={`${col.header} maximum`}
                className="h-7 w-full min-w-0 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-xs text-[var(--color-text-primary)] focus-visible:border-[var(--color-brand-accent)] focus-visible:outline-none"
              />
            </div>
            {col.rangePresets && col.rangePresets.length > 0 && (
              <div className="flex flex-wrap gap-1 px-2 pb-1">
                {col.rangePresets.map((preset) => (
                  <button
                    key={preset.label}
                    type="button"
                    onClick={() =>
                      onStateChange(withRange(state, col.key, { min: preset.min, max: preset.max }))
                    }
                    className="rounded-full border border-[var(--color-border)] px-2 py-0.5 text-[11px] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]"
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            )}
          </section>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// the saved-view menu (T35–T37)
// ---------------------------------------------------------------------------

function ViewMenu<T>({
  viewKey,
  state,
  onStateChange,
  close,
}: {
  viewKey: string
  state: FilterState
  onStateChange: (next: FilterState) => void
  close: () => void
}) {
  // The applied view id lives with the views in storage so the dirty dot
  // (T37) survives menu open/close and reloads, not just one mount.
  const [saved, setSaved] = useState<SavedViewCollection>(() => loadViews(viewKey))
  const { views, appliedId } = saved
  const [savingAs, setSavingAs] = useState(false)
  const [newName, setNewName] = useState('')
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')

  const persist = useCallback(
    (nextViews: SavedTableView[], nextAppliedId: string | null) => {
      setSaved({ views: nextViews, appliedId: nextAppliedId })
      persistViews(viewKey, nextViews, nextAppliedId)
    },
    [viewKey]
  )

  const appliedView = views.find((v) => v.id === appliedId) ?? null
  // T37: dirty = current state differs from the applied view's filters.
  const dirty = appliedView ? !filtersEqual(state, appliedView.filters) : countActiveFilters(state) > 0

  const applyView = (v: SavedTableView) => {
    onStateChange(v.filters)
    persist(views, v.id)
    close()
  }

  const saveAs = () => {
    const now = new Date().toISOString()
    const view: SavedTableView = {
      id: uid(),
      name: newName.trim() || 'Untitled view',
      filters: state,
      createdAt: now,
      updatedAt: now,
    }
    persist([...views, view], view.id)
    setSavingAs(false)
    setNewName('')
    close()
  }

  const updateApplied = () => {
    if (!appliedView) return
    persist(
      views.map((v) =>
        v.id === appliedView.id ? { ...v, filters: state, updatedAt: new Date().toISOString() } : v
      ),
      appliedView.id
    )
  }

  const commitRename = (v: SavedTableView) => {
    persist(
      views.map((x) =>
        x.id === v.id
          ? { ...x, name: renameValue.trim() || x.name, updatedAt: new Date().toISOString() }
          : x
      ),
      appliedId
    )
    setRenamingId(null)
  }

  const deleteView = (v: SavedTableView) => {
    persist(
      views.filter((x) => x.id !== v.id),
      appliedId === v.id ? null : appliedId
    )
  }

  const clearAll = () => {
    onStateChange(clearAllFilters(state))
    persist(views, null)
  }

  const onSaveKey = (e: ReactKeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') saveAs()
    if (e.key === 'Escape') {
      setSavingAs(false)
      setNewName('')
    }
  }

  return (
    <div className="w-64 p-1.5">
      <div className="flex items-center justify-between px-2 py-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">
          Views
        </span>
        {dirty && (
          <span
            className="h-1.5 w-1.5 rounded-full bg-[var(--color-warning)]"
            title="Unsaved changes"
            aria-label="Unsaved changes"
          />
        )}
      </div>

      {/* T37: a dirty applied view turns the menu entry into Update */}
      {appliedView && dirty && (
        <button
          type="button"
          onClick={updateApplied}
          className="w-full rounded-md px-2 py-1.5 text-left text-sm text-[var(--color-brand-accent)] hover:bg-[var(--color-surface-hover)]"
        >
          Update saved view
        </button>
      )}
      {/* T35: saving stays available even while a clean view is applied */}
      {!savingAs && !(appliedView && dirty) && (
        <button
          type="button"
          onClick={() => setSavingAs(true)}
          className="w-full rounded-md px-2 py-1.5 text-left text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]"
        >
          Save current as…
        </button>
      )}
      {savingAs && (
        <div className="p-1">
          <input
            autoFocus
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={onSaveKey}
            placeholder="View name"
            aria-label="View name"
            className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5 text-sm text-[var(--color-text-primary)] focus-visible:border-[var(--color-brand-accent)] focus-visible:outline-none"
          />
          <div className="mt-1.5 flex gap-1.5">
            <button
              type="button"
              onClick={saveAs}
              className="rounded-md bg-[var(--color-brand-accent)] px-2.5 py-1 text-xs font-medium text-white hover:opacity-90"
            >
              Save
            </button>
            <button
              type="button"
              onClick={() => {
                setSavingAs(false)
                setNewName('')
              }}
              className="rounded-md px-2.5 py-1 text-xs text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {views.length === 0 && !savingAs && (
        <p className="px-2 py-2 text-xs text-[var(--color-text-muted)]">No saved views yet.</p>
      )}

      {views.map((v) =>
        renamingId === v.id ? (
          <div key={v.id} className="p-1">
            <input
              autoFocus
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commitRename(v)
                if (e.key === 'Escape') setRenamingId(null)
              }}
              aria-label="Rename view input"
              className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1 text-sm text-[var(--color-text-primary)] focus-visible:border-[var(--color-brand-accent)] focus-visible:outline-none"
            />
          </div>
        ) : (
          <div
            key={v.id}
            className="group flex items-center gap-1 rounded-md px-1.5 hover:bg-[var(--color-surface-hover)]"
          >
            <button
              type="button"
              onClick={() => applyView(v)}
              className="flex min-w-0 flex-1 items-center gap-2 px-1 py-1.5 text-left text-sm"
            >
              <span
                aria-hidden="true"
                className={cn(
                  'h-1.5 w-1.5 shrink-0 rounded-full border',
                  appliedId === v.id
                    ? 'border-[var(--color-brand-accent)] bg-[var(--color-brand-accent)]'
                    : 'border-[var(--color-text-muted)] bg-transparent'
                )}
              />
              <span className="truncate">{v.name}</span>
            </button>
            {appliedId === v.id && dirty && (
              <span
                className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-warning)]"
                aria-label="Unsaved changes"
              />
            )}
            <button
              type="button"
              aria-label={`Rename ${v.name}`}
              onClick={() => {
                setRenamingId(v.id)
                setRenameValue(v.name)
              }}
              className="hidden h-6 w-6 shrink-0 items-center justify-center rounded-md text-[var(--color-text-muted)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text-primary)] group-hover:flex"
            >
              <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                />
              </svg>
            </button>
            <button
              type="button"
              aria-label={`Delete ${v.name}`}
              onClick={() => deleteView(v)}
              className="hidden h-6 w-6 shrink-0 items-center justify-center rounded-md text-[var(--color-text-muted)] hover:bg-[var(--color-surface)] hover:text-[var(--color-danger)] group-hover:flex"
            >
              <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                />
              </svg>
            </button>
          </div>
        )
      )}

      {countActiveFilters(state) > 0 && (
        <div className="mt-1 border-t border-[var(--color-divider)] pt-1">
          <button
            type="button"
            onClick={clearAll}
            className="w-full rounded-md px-2 py-1.5 text-left text-sm text-[var(--color-danger)] hover:bg-[var(--color-danger-light)]"
          >
            Clear filters
          </button>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// suggestions (T32 — the language is discoverable, not documented-or-else)
// ---------------------------------------------------------------------------

interface Suggestion {
  label: string
  term: string
}

/**
 * Distinct facet values per facet column, computed ONCE per data change —
 * suggestion building must not rescan the whole row set per keystroke.
 */
function useFacetVocabulary<T>(
  columns: Column<T>[],
  data: T[]
): Map<string, string[]> {
  return useMemo(() => {
    const map = new Map<string, string[]>()
    for (const col of columns) {
      if (!isFacetColumn(col)) continue
      map.set(col.key, facetCounts(data, col).map((o) => o.value))
    }
    return map
  }, [columns, data])
}

function buildSuggestions<T>(
  input: string,
  columns: Column<T>[],
  vocabulary: Map<string, string[]>
): Suggestion[] {
  const out: Suggestion[] = []
  const trimmed = input.trim()
  const bareWord = /^[A-Za-z]+$/.test(trimmed)

  for (const col of columns) {
    if (isFacetColumn(col)) {
      const values = vocabulary.get(col.key) ?? []
      if (bareWord) {
        const prefix = trimmed.toLowerCase()
        for (const value of values) {
          if (value.toLowerCase().startsWith(prefix)) {
            out.push({ label: value, term: value })
            if (out.length >= 4) return out
          }
        }
      } else {
        out.push({
          label: `${col.header}: ${values[0] ?? '<value>'}`,
          term: `${col.key.toLowerCase()}:${values[0] ?? ''}`,
        })
      }
    } else if (isRangeColumn(col) && /[><=]/.test(input)) {
      const sample = col.type === 'date' ? '2026-01-01' : col.type === 'progress' ? '50' : '5000'
      out.push({
        label: `${col.key.toLowerCase()} >= ${sample}`,
        term: `${col.key.toLowerCase()}>=${sample}`,
      })
    }
    if (out.length >= 5) break
  }
  return out
}

function bareFacetPrefix<T>(
  input: string,
  columns: Column<T>[],
  vocabulary: Map<string, string[]>
): boolean {
  if (!/^[A-Za-z]+$/.test(input.trim())) return false
  const prefix = input.trim().toLowerCase()
  return Array.from(vocabulary.values()).some((values) =>
    values.some((v) => v.toLowerCase().startsWith(prefix))
  )
}

// ---------------------------------------------------------------------------
// the rail
// ---------------------------------------------------------------------------

export function FilterRail<T>({
  columns,
  data,
  state,
  onStateChange,
  viewKey,
  placeholder = 'Search…',
  searchRef,
  className,
}: FilterRailProps<T>) {
  const [input, setInput] = useState(state.query)
  const [focused, setFocused] = useState(false)
  const [expandedChips, setExpandedChips] = useState(false)
  const vocabulary = useFacetVocabulary(columns, data)

  // external state changes (view applied, clear all) sync the input
  useEffect(() => {
    setInput(state.query)
  }, [state.query])

  // T28: 180ms debounce, then the row set changes (FLIP, never a skeleton)
  useEffect(() => {
    if (input === state.query) return
    const t = window.setTimeout(() => onStateChange({ ...state, query: input }), 180)
    return () => window.clearTimeout(t)
  }, [input, state, onStateChange])

  const facetChips = useMemo(
    () =>
      Object.entries(state.facets).flatMap(([colKey, values]) =>
        values.map((value) => ({ kind: 'facet' as const, colKey, value }))
      ),
    [state.facets]
  )
  const rangeChips = useMemo(
    () =>
      Object.entries(state.ranges).flatMap(([colKey, rng]) => {
        const col = columns.find((c) => c.key === colKey)
        if (!col || (rng.min === undefined && rng.max === undefined)) return []
        return [{ kind: 'range' as const, colKey, label: rangeChipLabel(col, rng as RangeFilter) }]
      }),
    [state.ranges, columns]
  )

  const chips = [...facetChips, ...rangeChips]
  const visibleChips = expandedChips ? chips : chips.slice(0, 6)
  const active = countActiveFilters(state)
  const showSuggestions =
    focused &&
    input.trim().length > 0 &&
    (bareFacetPrefix(input, columns, vocabulary) || /[><:=]/.test(input) || /\bor\b/i.test(input))
  const suggestions = useMemo(
    () => (showSuggestions ? buildSuggestions(input, columns, vocabulary) : []),
    [showSuggestions, input, columns, vocabulary]
  )

  return (
    <div className={cn('flex flex-col gap-2', className)}>
      <div className="flex items-center gap-2">
        <div className="relative w-80 max-w-full motion-safe:transition-[width] motion-safe:duration-[var(--motion-fast)] focus-within:w-[30rem]">
          <SearchInput
            ref={searchRef}
            value={input}
            onChange={(e) => {
              setInput(e.target.value)
              setExpandedChips(false)
            }}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onClear={() => {
              setInput('')
              onStateChange({ ...state, query: '' })
            }}
            placeholder={placeholder}
            aria-label="Filter table"
          />
          {suggestions.length > 0 && (
            <div
              role="listbox"
              className="absolute left-0 right-0 top-full z-[var(--z-dropdown)] mt-1.5 animate-fade-in-scale overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] py-1 shadow-xl"
            >
              <p className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">
                Completions
              </p>
              {suggestions.map((s) => (
                <button
                  key={s.term + s.label}
                  type="button"
                  role="option"
                  onMouseDown={(e) => {
                    // commit before blur hides the card
                    e.preventDefault()
                    setInput(s.term)
                    setExpandedChips(false)
                  }}
                  className="block w-full px-3 py-1.5 text-left font-mono text-xs text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)]"
                >
                  {s.label}
                </button>
              ))}
            </div>
          )}
        </div>

        <RailPopover
          trigger={
            <RailButton aria-label="Add filter" active={active > 0}>
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
                />
              </svg>
              Filter
              {active > 0 && (
                <span className="rounded-full bg-[var(--color-brand-accent)] px-1.5 text-[10px] font-semibold leading-4 text-white tabular-nums">
                  {active}
                </span>
              )}
            </RailButton>
          }
          className="w-fit"
        >
          {(close) => (
            <FilterPanel columns={columns} data={data} state={state} onStateChange={onStateChange} />
          )}
        </RailPopover>

        {viewKey && (
          <RailPopover
            trigger={
              <RailButton aria-label="Saved views">
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"
                  />
                </svg>
                View
              </RailButton>
            }
          >
            {(close) => (
              <ViewMenu viewKey={viewKey} state={state} onStateChange={onStateChange} close={close} />
            )}
          </RailPopover>
        )}
      </div>

      {chips.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          {visibleChips.map((chip) =>
            chip.kind === 'facet' ? (
              <Chip
                key={`${chip.colKey}:${chip.value}`}
                label={`${chip.colKey}: ${chip.value}`}
                onRemove={() => onStateChange(withFacet(state, chip.colKey, chip.value, false))}
              >
                {columns.find((c) => c.key === chip.colKey)?.header.toUpperCase() ?? chip.colKey}:{' '}
                <span className="font-medium text-[var(--color-text-primary)]">{chip.value}</span>
              </Chip>
            ) : (
              <Chip
                key={chip.colKey}
                label={chip.label}
                onRemove={() => onStateChange(clearRange(state, chip.colKey))}
              >
                <span className="tabular-nums">{chip.label}</span>
              </Chip>
            )
          )}
          {chips.length > 6 && (
            <button
              type="button"
              onClick={() => setExpandedChips((e) => !e)}
              className="rounded-full border border-[var(--color-border)] px-2.5 py-0.5 text-xs text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
            >
              {expandedChips ? 'Show less' : `+${chips.length - 6} more`}
            </button>
          )}
          {active > 0 && (
            <button
              type="button"
              onClick={() => {
                setExpandedChips(false)
                onStateChange(clearAllFilters(state))
              }}
              className="rounded-full px-2 py-0.5 text-xs font-medium text-[var(--color-text-muted)] underline-offset-2 hover:text-[var(--color-text-primary)] hover:underline"
            >
              Clear all
            </button>
          )}
        </div>
      )}
    </div>
  )
}


