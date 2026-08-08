import { useEffect, useMemo, type ReactNode, type Ref } from 'react'
import { cn } from '../../lib/utils'
import { EmptyState, ErrorState, Pagination } from '../ui'
import { DataTable, type Column } from '../ui/table'
import { applyFilters, clearAllFilters } from '../ui/table/filter-model'
import { applySort } from '../../lib/workspace/sort'
import { SelectionBar, WorkspaceToolbar } from './workspace-toolbar'
import type { UseWorkspaceResult } from './use-workspace'

/**
 * P8 — Data Workspace: the reusable composition for data-management pages.
 *
 * One workspace owns state (filters, sort, columns, density, page, selection
 * — see `useWorkspace`) and this component turns it into the full surface:
 *
 *  - the toolbar (sort / columns / density / refresh + module actions);
 *  - the selection bar with role-gated bulk actions;
 *  - the v3 `DataTable` (filter rail, saved views, FLIP, skeleton);
 *  - pagination and differentiated loading / error / empty states.
 *
 * Two modes:
 *  - `server` (default) — `data` is the current server page; filters page
 *    through `onFiltersChange` and the host refetches. Sorting is only
 *    available when the backend supports it (sortable columns present).
 *  - `local` — `data` is the full dataset; filtering, multi-column sorting
 *    and pagination all run client-side (directory-scale datasets).
 *
 * Features are opt-in: no bulk actions, no selection column; no sortable
 * columns, no sort UI; no `empty` config, the table's default empty state.
 */

export interface DataWorkspaceEmpty {
  title: string
  description: string
  actionLabel?: string
  onAction?: () => void
}

export interface DataWorkspaceProps<T> {
  /** The workspace state hook result — the page owns this and refetches. */
  workspace: UseWorkspaceResult<T>
  title: string
  description?: ReactNode
  columns: Column<T>[]
  keyExtractor: (item: T) => string | number
  /** Current server page (server mode) or the full dataset (local mode). */
  data: T[]
  total: number
  pages: number
  loading: boolean
  error: string | null
  onRetry: () => void
  /** Silent refetch — filters/sort/columns/pagination are preserved. */
  onRefresh: () => void
  mode?: 'server' | 'local'
  filterPlaceholder?: string
  onRowClick?: (item: T) => void
  /** The module's single primary action (e.g. Add Student). */
  primaryAction?: ReactNode
  /** Secondary actions rendered before the menus (e.g. Export). */
  toolbarActions?: ReactNode
  /**
   * Rendered inside the selection bar when rows are selected. Enabling this
   * switches the table's selection column on. Receives the selected rows
   * that are currently in `data` plus a clear-selection callback.
   */
  bulkActions?: (selected: T[], clearSelection: () => void) => ReactNode
  /** The \"no data exists\" state (distinct from \"no results match\"). */
  empty?: DataWorkspaceEmpty
  keyboardNav?: boolean
  /** Forwarded to the filter rail's search input (the `/` shortcut). */
  searchInputRef?: Ref<HTMLInputElement>
  className?: string
}

export function DataWorkspace<T>({
  workspace,
  title,
  description,
  columns,
  keyExtractor,
  data,
  total,
  pages,
  loading,
  error,
  onRetry,
  onRefresh,
  mode = 'server',
  filterPlaceholder = 'Search…',
  onRowClick,
  primaryAction,
  toolbarActions,
  bulkActions,
  empty,
  keyboardNav = true,
  searchInputRef,
  className,
}: DataWorkspaceProps<T>) {
  const {
    viewKey,
    filters,
    onFiltersChange,
    hasActiveFilters,
    sort,
    onSortChange,
    density,
    onDensityChange,
    isCompact,
    visibleColumns,
    visibleKeys,
    toggleColumn,
    resetColumns,
    page,
    setPage,
    size,
    setSize,
    selection,
    replaceSelection,
    clearSelection,
  } = workspace

  // Local mode: filter → multi-sort → paginate, all client-side.
  const filtered = useMemo(
    () => (mode === 'local' ? applyFilters(data, filters, columns) : data),
    [mode, data, filters, columns]
  )
  const sorted = useMemo(
    () => (mode === 'local' ? applySort(filtered, sort, columns) : filtered),
    [mode, filtered, sort, columns]
  )

  const totalRows = mode === 'local' ? sorted.length : total
  const totalPages = mode === 'local' ? Math.max(1, Math.ceil(totalRows / size)) : pages

  // Never strand the user on a page that filters shrank away.
  useEffect(() => {
    if (mode === 'local' && page > totalPages) setPage(totalPages)
  }, [mode, page, totalPages, setPage])

  const pageRows = useMemo(() => {
    if (mode === 'local') return sorted.slice((page - 1) * size, page * size)
    return data
  }, [mode, sorted, data, page, size])

  const selectedRows = useMemo(
    () => data.filter((item) => selection.has(keyExtractor(item))),
    [data, selection, keyExtractor]
  )

  const selectable = bulkActions !== undefined
  const showSelectionBar = selectable && selection.size > 0

  const footer = useMemo(() => {
    if (loading || totalRows === 0) return null
    const from = totalRows === 0 ? 0 : (page - 1) * size + 1
    const to = Math.min(page * size, totalRows)
    return (
      <div className="flex items-center justify-between px-1 pb-1 text-xs text-[var(--color-text-tertiary)]">
        <span>
          <span className="font-medium tabular-nums text-[var(--color-text-primary)]">
            {from.toLocaleString('en-US')}–{to.toLocaleString('en-US')}
          </span>{' '}
          of{' '}
          <span className="font-medium tabular-nums text-[var(--color-text-primary)]">
            {totalRows.toLocaleString('en-US')}
          </span>{' '}
          rows
        </span>
        {hasActiveFilters && (
          <button
            type="button"
            onClick={() => onFiltersChange(clearAllFilters(filters))}
            className="font-medium text-[var(--color-text-muted)] underline-offset-2 hover:text-[var(--color-text-primary)] hover:underline"
          >
            Clear all
          </button>
        )}
      </div>
    )
  }, [loading, totalRows, page, size, hasActiveFilters, filters, onFiltersChange])

  const emptyState =
    empty && totalRows === 0 && !hasActiveFilters && !loading ? (
      <div className="p-8">
        <EmptyState
          title={empty.title}
          description={empty.description}
          action={
            empty.actionLabel && empty.onAction
              ? { label: empty.actionLabel, onClick: empty.onAction }
              : undefined
          }
        />
      </div>
    ) : undefined

  return (
    <div className={cn('space-y-4', className)}>
      <WorkspaceToolbar
        title={title}
        description={description}
        columns={columns}
        sort={sort}
        onSortChange={onSortChange}
        density={density}
        onDensityChange={onDensityChange}
        visibleKeys={visibleKeys}
        onToggleColumn={toggleColumn}
        onResetColumns={resetColumns}
        onRefresh={onRefresh}
        toolbarActions={toolbarActions}
        primaryAction={primaryAction}
      />

      {showSelectionBar && (
        <SelectionBar count={selection.size} onClear={clearSelection}>
          {bulkActions?.(selectedRows, clearSelection)}
        </SelectionBar>
      )}

      {error ? (
        <ErrorState message={error} onRetry={onRetry} />
      ) : (
        <>
          <DataTable
            columns={visibleColumns}
            data={pageRows}
            keyExtractor={keyExtractor}
            loading={loading}
            filterable
            filters={filters}
            onFiltersChange={onFiltersChange}
            sort={sort}
            onSortChange={onSortChange}
            selectable={selectable}
            selectedKeys={selection}
            onSelectionChange={replaceSelection}
            keyboardNav={keyboardNav && (onRowClick !== undefined || selectable)}
            compact={isCompact}
            facetData={sorted}
            footer={footer ?? undefined}
            emptyContent={emptyState}
            emptyMessage={
              hasActiveFilters ? 'No rows match the current filters.' : 'No records yet'
            }
            filterPlaceholder={filterPlaceholder}
            filterInputRef={searchInputRef}
            viewKey={viewKey}
            onRowClick={onRowClick}
          />
          <Pagination
            page={page}
            size={size}
            total={totalRows}
            pages={totalPages}
            onPageChange={setPage}
            onSizeChange={(s) => {
              setSize(s)
              setPage(1)
            }}
          />
        </>
      )}
    </div>
  )
}
