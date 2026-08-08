import type { ReactNode } from 'react'
import { cn } from '../../../lib/utils'
import { TableSkeleton } from '../skeleton'

/**
 * Legacy `Table` — the original implementation, preserved verbatim so every
 * existing call site keeps running the exact code it ran before the v3 frame
 * landed (TABLE_SYSTEM_V3.md §19.1, step 1: "frame + types with zero visual
 * change").
 *
 * `DataTable` (frame.tsx) is the v3 instrument; the byte-parity tests in
 * `__tests__/table.test.tsx` verify the frame reproduces this markup exactly
 * for untyped columns.
 */

interface LegacyColumn<T> {
  key: string
  header: string
  render?: (item: T) => ReactNode
  className?: string
  sortable?: boolean
  hideOnMobile?: boolean
}

export interface TableProps<T> {
  columns: LegacyColumn<T>[]
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
      <div className="p-5">
        <TableSkeleton rows={5} cols={columns.length} />
      </div>
    )
  }

  if (data.length === 0) {
    return (
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
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full">
        <thead>
          <tr className={cn(stickyHeader && 'sticky top-0 z-[var(--z-sticky)]')}>
            {columns.map((col) => (
              <th
                key={col.key}
                className={cn(
                  'px-5 py-3.5 text-left text-xs font-semibold text-[var(--color-text-tertiary)] uppercase tracking-wider bg-[var(--color-bg)]',
                  compact ? 'py-2.5 text-[10px]' : '',
                  col.hideOnMobile && 'hidden lg:table-cell',
                  col.className
                )}
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
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--color-divider)]">
          {data.map((item, idx) => (
            <tr
              key={keyExtractor(item)}
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
                <td
                  key={col.key}
                  className={cn(
                    'px-5 text-sm text-[var(--color-text-primary)] whitespace-nowrap',
                    compact ? 'py-2.5' : 'py-3.5',
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
