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
  success: 'bg-[var(--color-success-light)] text-[var(--color-success-dark)]',
  warning: 'bg-[var(--color-warning-light)] text-[var(--color-warning-dark)]',
  danger: 'bg-[var(--color-danger-light)] text-[var(--color-danger-dark)]',
  info: 'bg-[var(--color-info-light)] text-[var(--color-info-dark)]',
  neutral: 'bg-[var(--color-surface-hover)] text-[var(--color-text-secondary)]',
  primary: 'bg-[var(--color-brand-accent-subtle)] text-[var(--color-brand-accent)]',
}

const sizes: Record<string, string> = {
  sm: 'px-1.5 py-0.5 text-[10px] leading-none',
  md: 'px-2 py-0.5 text-xs leading-none',
}

const dotColors: Record<BadgeVariant, string> = {
  success: 'bg-[var(--color-success)]',
  warning: 'bg-[var(--color-warning)]',
  danger: 'bg-[var(--color-danger)]',
  info: 'bg-[var(--color-info)]',
  neutral: 'bg-[var(--color-text-muted)]',
  primary: 'bg-[var(--color-brand-accent)]',
}

export function Badge({ variant = 'neutral', children, size = 'md', dot, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full font-medium',
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
