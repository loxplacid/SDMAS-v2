import type { CSSProperties, ReactNode } from 'react'
import { cn } from '../../lib/utils'

interface CardProps {
  title?: string
  subtitle?: string
  children: ReactNode
  className?: string
  style?: CSSProperties
  actions?: ReactNode
  onClick?: () => void
  padding?: 'none' | 'sm' | 'md' | 'lg'
  variant?: 'default' | 'elevated' | 'bordered' | 'flat'
}

const paddings = {
  none: '',
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-6',
}

const variants = {
  default: 'bg-[var(--color-surface)] border border-[var(--color-border)] shadow-sm',
  elevated: 'bg-[var(--color-surface)] border border-[var(--color-border)] shadow-md',
  bordered: 'bg-[var(--color-surface)] border-2 border-[var(--color-border)]',
  flat: 'bg-[var(--color-bg)] border border-[var(--color-border)]',
}

export function Card({
  title,
  subtitle,
  children,
  className,
  style,
  actions,
  onClick,
  padding = 'md',
  variant = 'default',
}: CardProps) {
  return (
    <div
      style={style}
      className={cn(
        'rounded-xl overflow-hidden',
        'transition-all motion-reduce:transition-none',
        'duration-[var(--motion-base)] ease-[var(--ease-standard)]',
        variants[variant],
        onClick
          ? 'cursor-pointer hover:-translate-y-0.5 hover:shadow-md hover:border-[var(--color-brand-accent)]/30 motion-reduce:hover:translate-y-0'
          : '',
        className
      )}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onClick()
              }
            }
          : undefined
      }
    >
      {(title || subtitle || actions) && (
        <div
          className={cn(
            'flex items-start justify-between gap-4',
            padding !== 'none' ? `px-${padding === 'lg' ? 6 : padding === 'sm' ? 3 : 4}` : 'px-4',
            'pt-4 pb-0'
          )}
        >
          <div className="min-w-0 flex-1">
            {title && (
              <h3 className="text-base font-semibold text-[var(--color-text-primary)] truncate">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="text-sm text-[var(--color-text-muted)] mt-0.5">{subtitle}</p>
            )}
          </div>
          {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
        </div>
      )}
      <div className={cn(paddings[padding])}>{children}</div>
    </div>
  )
}
