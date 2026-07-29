import { cn } from '../../lib/utils'

interface LoadingProps {
  text?: string
  className?: string
  size?: 'sm' | 'md' | 'lg'
  inline?: boolean
}

export function Loading({ text = 'Loading...', className, size = 'md', inline = false }: LoadingProps) {
  const sizes = {
    sm: 'h-4 w-4',
    md: 'h-6 w-6',
    lg: 'h-8 w-8',
  }

  const container = inline ? '' : 'flex flex-col items-center justify-center py-12'

  return (
    <div className={cn(container, className)} role="status" aria-label={text}>
      <svg
        className={cn('animate-spin text-[var(--color-primary)]', sizes[size], !inline && 'mb-3')}
        fill="none"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      {!inline && <p className="text-sm text-[var(--color-text-muted)]" aria-hidden="true">{text}</p>}
    </div>
  )
}
