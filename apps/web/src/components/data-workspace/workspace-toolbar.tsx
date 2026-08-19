import { useState, type ReactNode } from 'react'
import { cn } from '../../lib/utils'
import { DropdownMenu, type DropdownItem } from '../ui/dropdown-menu'
import type { Column } from '../ui/table/columns'
import type { SortRule } from '../ui/table'
import { RailPopover } from '../ui/table/filter-rail'
import { cycleSort } from '../../lib/workspace/sort'
import type { WorkspaceDensity } from './use-workspace'

/**
 * P8 — Data Workspace toolbar controls.
 *
 * Everything here is a small opt-in control over the shared `DropdownMenu`:
 *  - Sort — lists sortable columns with their active direction/rank; a click
 *    cycles the primary rule; Shift-click on a header adds secondaries.
 *  - Columns — show/hide with one-position reorder handles + reset (P12).
 *  - Density — comfortable / compact / dense, persisted per module (P12).
 *  - Refresh — silent refetch with a brief spin.
 *
 * The search box, filter builder and saved views live in the table's filter
 * rail — one toolbar, two surfaces, no duplication.
 */

function ToolbarButton({
  label,
  active = false,
  onClick,
  children,
}: {
  label: string
  active?: boolean
  onClick?: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className={cn(
        'inline-flex h-8 items-center gap-1.5 rounded-lg border px-2.5 text-xs font-medium',
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

function CheckIcon() {
  return (
    <svg className="h-3.5 w-3.5 text-[var(--color-brand-accent)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
    </svg>
  )
}

function SortGlyph({ direction, rank }: { direction: 'asc' | 'desc'; rank: number }) {
  return (
    <span className="inline-flex items-center gap-0.5 text-[var(--color-brand-accent)]">
      <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        {direction === 'asc' ? (
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
        ) : (
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        )}
      </svg>
      <span className="text-[9px] font-bold tabular-nums">{rank}</span>
    </span>
  )
}

export interface WorkspaceToolbarProps<T> {
  title: string
  description?: ReactNode
  columns: Column<T>[]
  sort: SortRule[]
  onSortChange: (next: SortRule[]) => void
  density: WorkspaceDensity
  onDensityChange: (next: WorkspaceDensity) => void
  visibleKeys: ReadonlySet<string>
  /** Visible column keys in display order (P12 — reorder). */
  visibleOrder: readonly string[]
  onToggleColumn: (key: string) => void
  onMoveColumn: (key: string, dir: -1 | 1) => void
  onResetColumns: () => void
  onRefresh?: () => void
  /** Secondary actions (e.g. Export) rendered before the menus. */
  toolbarActions?: ReactNode
  /** The module's single primary action. */
  primaryAction?: ReactNode
}

export function WorkspaceToolbar<T>({
  title,
  description,
  columns,
  sort,
  onSortChange,
  density,
  onDensityChange,
  visibleKeys,
  visibleOrder,
  onToggleColumn,
  onMoveColumn,
  onResetColumns,
  onRefresh,
  toolbarActions,
  primaryAction,
}: WorkspaceToolbarProps<T>) {
  const sortable = columns.filter((c) => c.sortable)
  const toggleable = columns.filter(
    (c) =>
      c.type !== 'actions' && c.type !== 'checkbox' && c.type !== 'expander' && !c.key.startsWith('__')
  )

  const sortItems: DropdownItem[] = [
    ...sortable.map((col) => {
      const rank = sort.findIndex((r) => r.key === col.key)
      const rule = rank >= 0 ? sort[rank] : undefined
      return {
        id: `sort-${col.key}`,
        label: col.header,
        icon: rule ? <SortGlyph direction={rule.direction} rank={rank + 1} /> : undefined,
        onClick: () => onSortChange(cycleSort(sort, col.key, false)),
      }
    }),
    ...(sort.length > 0
      ? [{ id: 'sort-clear', label: 'Clear sorting', danger: true as const, onClick: () => onSortChange([]) }]
      : []),
  ]

  const densityItems: DropdownItem[] = [
    {
      id: 'density-comfortable',
      label: 'Comfortable',
      icon: density === 'comfortable' ? <CheckIcon /> : undefined,
      onClick: () => onDensityChange('comfortable'),
    },
    {
      id: 'density-compact',
      label: 'Compact',
      icon: density === 'compact' ? <CheckIcon /> : undefined,
      onClick: () => onDensityChange('compact'),
    },
    {
      id: 'density-dense',
      label: 'Dense',
      icon: density === 'dense' ? <CheckIcon /> : undefined,
      onClick: () => onDensityChange('dense'),
    },
  ]

  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
      <div className="min-w-0">
        <h2 className="text-xl font-bold text-[var(--color-text-primary)] tracking-tight">{title}</h2>
        {description && <p className="mt-1 text-sm text-[var(--color-text-tertiary)]">{description}</p>}
      </div>

      <div className="flex items-center gap-2">
        {toolbarActions}
        {sortable.length > 0 && (
          <DropdownMenu
            items={sortItems}
            position="bottom-right"
            trigger={
              <ToolbarButton label="Sort columns" active={sort.length > 0}>
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
                </svg>
                Sort
                {sort.length > 0 && (
                  <span className="rounded-full bg-[var(--color-brand-accent)] px-1.5 text-[10px] font-semibold leading-4 text-white tabular-nums">
                    {sort.length}
                  </span>
                )}
              </ToolbarButton>
            }
          />
        )}
        <RailPopover
          trigger={
            <ToolbarButton label="Manage columns">
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
              </svg>
              Columns
            </ToolbarButton>
          }
        >
          {(close) => (
            <ColumnMenu
              columns={toggleable}
              visibleKeys={visibleKeys}
              visibleOrder={visibleOrder}
              onToggleColumn={onToggleColumn}
              onMoveColumn={onMoveColumn}
              onResetColumns={() => {
                onResetColumns()
                close()
              }}
            />
          )}
        </RailPopover>
        <DropdownMenu
          items={densityItems}
          position="bottom-right"
          trigger={
            <ToolbarButton label="Table density">
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5h16M4 10h16M4 15h16M4 20h16" />
              </svg>
            </ToolbarButton>
          }
        />
        {onRefresh && (
          <RefreshButton onRefresh={onRefresh} />
        )}
        {primaryAction}
      </div>
    </div>
  )
}

/** P12 §5 — one-position reorder handle inside the columns menu. */
function MoveButton({
  label,
  dir,
  disabled,
  onClick,
}: {
  label: string
  dir: 'left' | 'right'
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={(e) => {
        // never let the handle toggle the column — the row click owns that
        e.stopPropagation()
        onClick()
      }}
      className="flex h-5 w-5 shrink-0 items-center justify-center rounded text-[var(--color-text-muted)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text-primary)] disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-[var(--color-text-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-brand-accent-ring)]"
    >
      <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        {dir === 'left' ? (
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        ) : (
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        )}
      </svg>
    </button>
  )
}

/**
 * P12 §5 — the columns menu: show/hide (click a row), reorder (←/→ handles
 * on visible rows) and reset-to-defaults. Visible rows render in the current
 * display order so the handles are unambiguous.
 */
function ColumnMenu<T>({
  columns,
  visibleKeys,
  visibleOrder,
  onToggleColumn,
  onMoveColumn,
  onResetColumns,
}: {
  columns: Column<T>[]
  visibleKeys: ReadonlySet<string>
  visibleOrder: readonly string[]
  onToggleColumn: (key: string) => void
  onMoveColumn: (key: string, dir: -1 | 1) => void
  onResetColumns: () => void
}) {
  const byKey = new Map(columns.map((c) => [c.key, c] as const))
  const visible = visibleOrder
    .map((key) => byKey.get(key))
    .filter((c): c is Column<T> => c !== undefined)
  const hidden = columns.filter((c) => !visibleKeys.has(c.key))

  return (
    // A labelled group of real toggle buttons (aria-pressed), not a menu:
    // each row carries two reorder buttons plus a visibility toggle, which a
    // `role=menuitem` cannot legally contain. Every control is a real,
    // natively-activatable button — no nested-handler keydown traps.
    <div role="group" aria-label="Column options" className="w-64 p-1.5">
      <p className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">
        Visible
      </p>
      {visible.map((col, idx) => (
        <div
          key={col.key}
          className="group flex items-center gap-0.5 rounded-md px-1 hover:bg-[var(--color-surface-hover)]"
        >
          <MoveButton
            label={`Move ${col.header} left`}
            dir="left"
            disabled={idx === 0}
            onClick={() => onMoveColumn(col.key, -1)}
          />
          <MoveButton
            label={`Move ${col.header} right`}
            dir="right"
            disabled={idx === visible.length - 1}
            onClick={() => onMoveColumn(col.key, 1)}
          />
          <button
            type="button"
            aria-pressed="true"
            onClick={() => onToggleColumn(col.key)}
            className="flex min-w-0 flex-1 items-center gap-2 rounded px-1 py-1.5 text-left text-sm text-[var(--color-text-primary)] hover:bg-[var(--color-surface)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-brand-accent-ring)]"
          >
            <CheckIcon />
            <span className="truncate">{col.header}</span>
          </button>
        </div>
      ))}
      {visible.length === 0 && (
        <p className="px-2 py-1.5 text-xs text-[var(--color-text-muted)]">All columns hidden.</p>
      )}

      {hidden.length > 0 && (
        <>
          <p className="px-2 pb-1 pt-1.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">
            Hidden
          </p>
          {hidden.map((col) => (
            <button
              key={col.key}
              type="button"
              aria-pressed="false"
              onClick={() => onToggleColumn(col.key)}
              className="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-left text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-brand-accent-ring)]"
            >
              <svg className="h-3.5 w-3.5 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              <span className="truncate">{col.header}</span>
            </button>
          ))}
        </>
      )}

      <div className="my-1 mx-2 border-t border-[var(--color-divider)]" aria-hidden="true" />
      <button
        type="button"
        onClick={onResetColumns}
        className="w-full rounded-md px-2 py-1.5 text-left text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-brand-accent-ring)]"
      >
        Reset to defaults
      </button>
    </div>
  )
}

function RefreshButton({ onRefresh }: { onRefresh: () => void }) {
  const [spinning, setSpinning] = useState(false)
  return (
    <ToolbarButton
      label="Refresh data"
      onClick={() => {
        setSpinning(true)
        onRefresh()
        window.setTimeout(() => setSpinning(false), 700)
      }}
    >
      <svg
        className={cn('h-3.5 w-3.5', spinning && 'animate-spin')}
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
      </svg>
    </ToolbarButton>
  )
}

/** P8 §11 — the contextual toolbar that appears while rows are selected. */
export function SelectionBar({
  count,
  onClear,
  children,
}: {
  count: number
  onClear: () => void
  children?: ReactNode
}) {
  return (
    <div
      className="flex flex-wrap items-center gap-2 rounded-xl border border-[var(--color-brand-accent)]/30 bg-[var(--color-brand-accent-subtle)] px-3 py-2 animate-fade-in"
      role="toolbar"
      aria-label="Selection actions"
    >
      <span className="text-sm font-medium text-[var(--color-brand-accent)] tabular-nums">
        {count} selected
      </span>
      {children && (
        <span className="mx-1 h-4 w-px bg-[var(--color-brand-accent)]/25" aria-hidden="true" />
      )}
      {children}
      <button
        type="button"
        onClick={onClear}
        className="ml-auto text-xs font-medium text-[var(--color-text-muted)] underline-offset-2 hover:text-[var(--color-text-primary)] hover:underline"
      >
        Clear selection
      </button>
    </div>
  )
}
