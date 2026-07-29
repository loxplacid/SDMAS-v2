import { Button } from './button'

interface PaginationProps {
  page: number
  size: number
  total: number
  pages: number
  onPageChange: (page: number) => void
  onSizeChange?: (size: number) => void
}

export function Pagination({ page, size, total, pages, onPageChange, onSizeChange }: PaginationProps) {
  if (pages <= 1 && total <= size) return null

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-4 py-3 border-t border-[var(--color-border)]">
      <div className="flex items-center gap-3 text-sm text-[var(--color-text-secondary)]">
        <span>
          Showing{' '}
          <span className="font-medium">{(page - 1) * size + 1}</span>
          {' '}-{' '}
          <span className="font-medium">{Math.min(page * size, total)}</span>
          {' '}of{' '}
          <span className="font-medium">{total.toLocaleString()}</span>
        </span>
        {onSizeChange && (
          <div className="flex items-center gap-1.5">
            <span className="text-[var(--color-text-muted)]">|</span>
            <select
              value={size}
              onChange={(e) => onSizeChange(Number(e.target.value))}
              className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1 text-xs text-[var(--color-text-primary)] focus:border-[var(--color-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
              aria-label="Page size"
            >
              {[10, 20, 50, 100].map((n) => (
                <option key={n} value={n}>
                  {n} / page
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="flex items-center gap-1">
        <Button
          variant="outline"
          size="sm"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          aria-label="Previous page"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </Button>

        {getPageNumbers(page, pages).map((p, idx) => {
          if (typeof p === 'string') {
            return (
              <span key={`ellipsis-${idx}`} className="px-1 text-sm text-[var(--color-text-muted)]">
                ...
              </span>
            )
          }
          return (
            <Button
              key={p}
              variant={p === page ? 'primary' : 'outline'}
              size="xs"
              onClick={() => onPageChange(p)}
              aria-label={`Page ${p}`}
              aria-current={p === page ? 'page' : undefined}
            >
              {p}
            </Button>
          )
        })}

        <Button
          variant="outline"
          size="sm"
          disabled={page >= pages}
          onClick={() => onPageChange(page + 1)}
          aria-label="Next page"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </Button>
      </div>
    </div>
  )
}

function getPageNumbers(current: number, total: number): (number | string)[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1)
  }

  const pages: (number | string)[] = []

  if (current <= 4) {
    for (let i = 1; i <= 5; i++) pages.push(i)
    pages.push('...')
    pages.push(total)
  } else if (current >= total - 3) {
    pages.push(1)
    pages.push('...')
    for (let i = total - 4; i <= total; i++) pages.push(i)
  } else {
    pages.push(1)
    pages.push('...')
    pages.push(current - 1)
    pages.push(current)
    pages.push(current + 1)
    pages.push('...')
    pages.push(total)
  }

  return pages
}
