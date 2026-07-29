import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

export type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'primary'

interface BadgeProps {
  variant?: BadgeVariant
  children: ReactNode
  size?: 'sm' | 'md'
  dot?: boolean
  className?: string
}

const variants: Record<BadgeVariant, string> = {
  success: 'bg-[var(--color-success-light)] text-[var(--color-success-dark)] ring-1 ring-inset ring-[var(--color-success)]/20',
  warning: 'bg-[var(--color-warning-light)] text-[var(--color-warning-dark)] ring-1 ring-inset ring-[var(--color-warning)]/20',
  danger: 'bg-[var(--color-danger-light)] text-[var(--color-danger-dark)] ring-1 ring-inset ring-[var(--color-danger)]/20',
  info: 'bg-[var(--color-info-light)] text-[var(--color-info-dark)] ring-1 ring-inset ring-[var(--color-info)]/20',
  neutral: 'bg-[var(--color-surface-hover)] text-[var(--color-text-secondary)] ring-1 ring-inset ring-[var(--color-border)]',
  primary: 'bg-[var(--color-primary-light)] text-[var(--color-primary-dark)] ring-1 ring-inset ring-[var(--color-primary)]/20',
}

const sizes: Record<string, string> = {
  sm: 'px-1.5 py-0.5 text-[10px]',
  md: 'px-2 py-0.5 text-xs',
}

const dotColors: Record<BadgeVariant, string> = {
  success: 'bg-[var(--color-success)]',
  warning: 'bg-[var(--color-warning)]',
  danger: 'bg-[var(--color-danger)]',
  info: 'bg-[var(--color-info)]',
  neutral: 'bg-[var(--color-text-muted)]',
  primary: 'bg-[var(--color-primary)]',
}

export function Badge({ variant = 'neutral', children, size = 'md', dot, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full font-medium leading-none',
        variants[variant],
        sizes[size],
        className
      )}
    >
      {dot && (
        <span className={cn('h-1.5 w-1.5 rounded-full', dotColors[variant])} aria-hidden="true" />
      )}
      {children}
    </span>
  )
}
