import { useState, type ReactNode } from 'react'
import { cn } from '../../lib/utils'
import { DropdownMenu, type DropdownItem } from '../ui/dropdown-menu'
import type { Column } from '../ui/table/columns'
import type { SortRule } from '../ui/table'
import { cycleSort } from '../../lib/workspace/sort'
import type { WorkspaceDensity } from './use-workspace'

/**
 * P8 — Data Workspace toolbar controls.
 *
 * Everything here is a small opt-in control over the shared `DropdownMenu`:
 *  - Sort — lists sortable columns with their active direction/rank; a click
 *    cycles the primary rule; Shift-click on a header adds secondaries.
 *  - Columns — show/hide columns with reset-to-defaults.
 *  - Density — comfortable / compact, persisted per module.
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
        'inline-flex h-8 items-center gap-1.5 rounded-[10px] border px-2.5 text-xs font-medium',
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
  onToggleColumn: (key: string) => void
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
  onToggleColumn,
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

  const columnItems: DropdownItem[] = [
    ...toggleable.map((col) => ({
      id: `col-${col.key}`,
      label: col.header,
      icon: visibleKeys.has(col.key) ? <CheckIcon /> : undefined,
      onClick: () => onToggleColumn(col.key),
    })),
    { id: 'col-divider', label: '', divider: true },
    { id: 'col-reset', label: 'Reset to defaults', onClick: onResetColumns },
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
        <DropdownMenu
          items={columnItems}
          position="bottom-right"
          trigger={
            <ToolbarButton label="Manage columns">
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
              </svg>
              Columns
            </ToolbarButton>
          }
        />
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
