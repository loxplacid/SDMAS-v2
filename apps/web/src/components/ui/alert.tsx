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
  info: 'bg-[var(--color-info-light)] border-[var(--color-info)]/30 text-[var(--color-info-dark)]',
  success: 'bg-[var(--color-success-light)] border-[var(--color-success)]/30 text-[var(--color-success-dark)]',
  warning: 'bg-[var(--color-warning-light)] border-[var(--color-warning)]/30 text-[var(--color-warning-dark)]',
  error: 'bg-[var(--color-danger-light)] border-[var(--color-danger)]/30 text-[var(--color-danger-dark)]',
}

const icons = {
  info: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  success: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  warning: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
  error: 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z',
}

export function Alert({ variant = 'info', children, onClose, className = '', title }: AlertProps) {
  return (
    <div
      className={cn(
        'rounded-lg border p-4 text-sm animate-slide-in-from-top',
        variants[variant],
        className
      )}
      role="alert"
    >
      <div className="flex items-start gap-3">
        <svg
          className="h-5 w-5 flex-shrink-0 mt-0.5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={icons[variant]} />
        </svg>
        <div className="flex-1 min-w-0">
          {title && <p className="font-medium mb-1">{title}</p>}
          <div>{children}</div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="flex-shrink-0 flex items-center justify-center h-6 w-6 rounded-md hover:bg-black/5 transition-colors"
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
