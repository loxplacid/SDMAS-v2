import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'
import { TableSkeleton } from './skeleton'

interface Column<T> {
  key: string
  header: string
  render?: (item: T) => ReactNode
  className?: string
  sortable?: boolean
  hideOnMobile?: boolean
}

interface TableProps<T> {
  columns: Column<T>[]
  data: T[]
  keyExtractor: (item: T) => string | number
  loading?: boolean
  emptyMessage?: string
  onRowClick?: (item: T) => void
  stickyHeader?: boolean
  compact?: boolean
}

export function Table<T>({
  columns,
  data,
  keyExtractor,
  loading,
  emptyMessage = 'No data',
  onRowClick,
  stickyHeader = true,
  compact = false,
}: TableProps<T>) {
  if (loading) {
    return (
      <div className="p-4">
        <TableSkeleton rows={5} cols={columns.length} />
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center animate-fade-in">
        <svg className="h-10 w-10 text-[var(--color-text-muted)] mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
        </svg>
        <p className="text-sm text-[var(--color-text-muted)]">{emptyMessage}</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto -mx-4 sm:-mx-0">
      <table className="min-w-full divide-y divide-[var(--color-border)]">
        <thead>
          <tr className={cn(stickyHeader && 'sticky top-0 z-10')}>
            {columns.map((col) => (
              <th
                key={col.key}
                className={cn(
                  'px-4 py-3 text-left text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider bg-[var(--color-bg)]',
                  compact ? 'py-2 text-[10px]' : 'py-3',
                  col.hideOnMobile && 'hidden lg:table-cell',
                  col.className
                )}
              >
                <div className="flex items-center gap-1">
                  {col.header}
                  {col.sortable && (
                    <svg className="h-3 w-3 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
                    </svg>
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--color-border)]">
          {data.map((item, idx) => (
            <tr
              key={keyExtractor(item)}
              className={cn(
                'transition-all motion-reduce:transition-none duration-[var(--motion-fast)] ease-[var(--ease-standard)]',
                'animate-fade-in',
                onRowClick && 'cursor-pointer',
                idx % 2 === 0 ? 'bg-[var(--color-surface)]' : 'bg-[var(--color-bg)]/50',
                onRowClick && 'hover:bg-[var(--color-brand-accent-subtle)] hover:brightness-[0.99]'
              )}
              style={{ animationDelay: `${Math.min(idx * 20, 300)}ms`, animationFillMode: 'both' }}
              onClick={() => onRowClick?.(item)}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={cn(
                    'px-4 text-sm text-[var(--color-text-primary)] whitespace-nowrap',
                    compact ? 'py-2' : 'py-3',
                    col.hideOnMobile && 'hidden lg:table-cell',
                    col.className
                  )}
                >
                  {col.render ? col.render(item) : (item as any)[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
