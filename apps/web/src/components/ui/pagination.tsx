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
    <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200">
      <div className="flex items-center gap-2 text-sm text-gray-700">
        <span>Showing {(page - 1) * size + 1}-{Math.min(page * size, total)} of {total}</span>
        {onSizeChange && (
          <select
            value={size}
            onChange={(e) => onSizeChange(Number(e.target.value))}
            className="ml-2 rounded border border-gray-300 px-2 py-1 text-sm"
          >
            {[10, 20, 50, 100].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        )}
      </div>
      <div className="flex items-center gap-1">
        <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          Previous
        </Button>
        {Array.from({ length: Math.min(pages, 5) }, (_, i) => {
          const start = Math.max(1, Math.min(page - 2, pages - 4))
          const p = start + i
          if (p > pages) return null
          return (
            <Button
              key={p}
              variant={p === page ? 'primary' : 'secondary'}
              size="sm"
              onClick={() => onPageChange(p)}
            >
              {p}
            </Button>
          )
        })}
        <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => onPageChange(page + 1)}>
          Next
        </Button>
      </div>
    </div>
  )
}