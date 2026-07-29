import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cn } from '../../lib/utils'

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost' | 'outline' | 'success' | 'warning'
type Size = 'xs' | 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  children: ReactNode
}

const variants: Record<Variant, string> = {
  primary:
    'bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-hover)] focus:ring-[var(--color-primary)] shadow-sm',
  secondary:
    'bg-[var(--color-secondary)] text-white hover:bg-[var(--color-secondary-hover)] focus:ring-[var(--color-secondary)] shadow-sm',
  danger:
    'bg-[var(--color-danger)] text-white hover:bg-[var(--color-danger-dark)] focus:ring-[var(--color-danger)] shadow-sm',
  success:
    'bg-[var(--color-success)] text-white hover:bg-[var(--color-success-dark)] focus:ring-[var(--color-success)] shadow-sm',
  warning:
    'bg-[var(--color-warning)] text-white hover:bg-[var(--color-warning-dark)] focus:ring-[var(--color-warning)] shadow-sm',
  ghost:
    'bg-transparent text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] focus:ring-[var(--color-primary)]',
  outline:
    'bg-transparent text-[var(--color-text-primary)] border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] hover:border-[var(--color-primary)] focus:ring-[var(--color-primary)]',
}

const sizes: Record<Size, string> = {
  xs: 'px-2 py-1 text-xs gap-1',
  sm: 'px-2.5 py-1.5 text-xs gap-1.5',
  md: 'px-3.5 py-2 text-sm gap-2',
  lg: 'px-5 py-2.5 text-base gap-2',
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled,
  className,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-lg font-medium',
        'transition-all motion-reduce:transition-none',
        'active:scale-[0.97] motion-reduce:active:scale-100',
        'focus:outline-none focus:ring-2 focus:ring-offset-2',
        'disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none disabled:active:scale-100',
        variants[variant],
        sizes[size],
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <svg
          className="animate-spin h-4 w-4 flex-shrink-0"
          fill="none"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
      <span className={cn('inline-flex items-center gap-2', loading && 'opacity-90')}>
        {children}
      </span>
    </button>
  )
}
