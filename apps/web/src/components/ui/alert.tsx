import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

interface AlertProps {
  variant?: 'info' | 'success' | 'warning' | 'error'
  children: ReactNode
  onClose?: () => void
  className?: string
  title?: string
}

const variants = {
  info: 'bg-[var(--color-info-light)] border-l-[var(--color-info)] text-[var(--color-info-dark)]',
  success: 'bg-[var(--color-success-light)] border-l-[var(--color-success)] text-[var(--color-success-dark)]',
  warning: 'bg-[var(--color-warning-light)] border-l-[var(--color-warning)] text-[var(--color-warning-dark)]',
  error: 'bg-[var(--color-danger-light)] border-l-[var(--color-danger)] text-[var(--color-danger-dark)]',
}

export function Alert({ variant = 'info', children, onClose, className = '', title }: AlertProps) {
  return (
    <div
      className={cn(
        'rounded-xl border-l-[3px] p-4 text-sm animate-slide-down',
        variants[variant],
        className
      )}
      role="alert"
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          {title && <p className="font-semibold mb-1">{title}</p>}
          <div>{children}</div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="flex-shrink-0 flex items-center justify-center h-6 w-6 rounded-lg hover:bg-black/5 motion-safe:transition-colors"
            aria-label="Dismiss"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>
    </div>
  )
}
