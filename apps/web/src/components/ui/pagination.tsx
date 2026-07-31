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
    <div className="flex flex-col sm:flex-row items-center justify-between gap-4 px-5 py-4 border-t border-[var(--color-divider)]">
      <div className="flex items-center gap-3 text-sm text-[var(--color-text-secondary)]">
        <span>
          <span className="font-medium text-[var(--color-text-primary)]">{(page - 1) * size + 1}</span>
          <span className="text-[var(--color-text-tertiary)]"> – </span>
          <span className="font-medium text-[var(--color-text-primary)]">{Math.min(page * size, total)}</span>
          <span className="text-[var(--color-text-tertiary)]"> of </span>
          <span className="font-medium text-[var(--color-text-primary)]">{total.toLocaleString()}</span>
        </span>
        {onSizeChange && (
          <div className="flex items-center gap-1.5">
            <span className="text-[var(--color-text-tertiary)] ml-1">·</span>
            <select
              value={size}
              onChange={(e) => onSizeChange(Number(e.target.value))}
              className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1 text-xs text-[var(--color-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-brand-accent-ring)]"
              aria-label="Page size"
            >
              {[10, 20, 50, 100].map((n) => (
                <option key={n} value={n}>{n} / page</option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="flex items-center gap-1">
        <Button variant="secondary" size="xs" disabled={page <= 1} onClick={() => onPageChange(page - 1)} aria-label="Previous page">
          <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </Button>

        {getPageNumbers(page, pages).map((p, idx) =>
          typeof p === 'string' ? (
            <span key={`e-${idx}`} className="px-1 text-sm text-[var(--color-text-tertiary)]">···</span>
          ) : (
            <Button
              key={p}
              variant={p === page ? 'primary' : 'secondary'}
              size="xs"
              onClick={() => onPageChange(p)}
              aria-label={`Page ${p}`}
              aria-current={p === page ? 'page' : undefined}
            >
              {p}
            </Button>
          )
        )}

        <Button variant="secondary" size="xs" disabled={page >= pages} onClick={() => onPageChange(page + 1)} aria-label="Next page">
          <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </Button>
      </div>
    </div>
  )
}

function getPageNumbers(current: number, total: number): (number | string)[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages: (number | string)[] = []
  if (current <= 4) {
    for (let i = 1; i <= 5; i++) pages.push(i)
    pages.push('...'); pages.push(total)
  } else if (current >= total - 3) {
    pages.push(1); pages.push('...')
    for (let i = total - 4; i <= total; i++) pages.push(i)
  } else {
    pages.push(1); pages.push('...')
    pages.push(current - 1, current, current + 1)
    pages.push('...'); pages.push(total)
  }
  return pages
}
