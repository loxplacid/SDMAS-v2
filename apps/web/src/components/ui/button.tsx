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
    'bg-[var(--color-brand-accent)] text-white hover:bg-[var(--color-brand-accent-hover)] ' +
    'shadow-sm hover:shadow-md active:shadow-sm ' +
    'focus-visible:ring-2 focus-visible:ring-[var(--color-brand-accent-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg)]',
  secondary:
    'bg-[var(--color-surface)] text-[var(--color-text-primary)] border border-[var(--color-border)] ' +
    'hover:bg-[var(--color-surface-hover)] hover:border-[var(--color-border-hover)] ' +
    'shadow-sm active:shadow-none ' +
    'focus-visible:ring-2 focus-visible:ring-[var(--color-brand-accent-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg)]',
  danger:
    'bg-[var(--color-danger)] text-white hover:bg-[var(--color-danger-dark)] ' +
    'shadow-sm hover:shadow-md active:shadow-sm ' +
    'focus-visible:ring-2 focus-visible:ring-[var(--color-danger-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg)]',
  success:
    'bg-[var(--color-success)] text-white hover:bg-[var(--color-success-dark)] ' +
    'shadow-sm hover:shadow-md active:shadow-sm ' +
    'focus-visible:ring-2 focus-visible:ring-[var(--color-success-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg)]',
  warning:
    'bg-[var(--color-warning)] text-white hover:bg-[var(--color-warning-dark)] ' +
    'shadow-sm hover:shadow-md active:shadow-sm ' +
    'focus-visible:ring-2 focus-visible:ring-[var(--color-warning-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg)]',
  ghost:
    'bg-transparent text-[var(--color-text-secondary)] ' +
    'hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] ' +
    'focus-visible:ring-2 focus-visible:ring-[var(--color-brand-accent-ring)]',
  outline:
    'bg-transparent text-[var(--color-text-primary)] border border-[var(--color-border)] ' +
    'hover:bg-[var(--color-surface-hover)] hover:border-[var(--color-brand-accent)] hover:text-[var(--color-brand-accent)] ' +
    'focus-visible:ring-2 focus-visible:ring-[var(--color-brand-accent-ring)]',
}

const sizes: Record<Size, string> = {
  xs: 'px-2.5 py-1 text-[11px] gap-1.5 leading-none',
  sm: 'px-3 py-1.5 text-xs gap-1.5 leading-none',
  md: 'px-4 py-2 text-sm gap-2 leading-snug',
  lg: 'px-6 py-2.5 text-[15px] gap-2 leading-snug',
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
        'inline-flex items-center justify-center rounded-[10px] font-medium',
        'motion-safe:transition-all motion-safe:duration-[var(--motion-fast)] motion-safe:ease-[var(--ease-standard)]',
        'motion-safe:active:scale-[0.97]',
        'focus-visible:outline-none',
        'disabled:opacity-45 disabled:pointer-events-none disabled:shadow-none',
        variants[variant],
        sizes[size],
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <svg
          className="animate-spin h-[1em] w-[1em] flex-shrink-0"
          fill="none"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
      <span className={cn('inline-flex items-center gap-1.5', loading && 'opacity-90')}>
        {children}
      </span>
    </button>
  )
}
