import { cn } from '../../lib/utils'

interface LoadingProps {
  text?: string
  className?: string
  size?: 'sm' | 'md' | 'lg'
  inline?: boolean
}

export function Loading({ text = 'Loading...', className, size = 'md', inline = false }: LoadingProps) {
  const sizes = { sm: 'h-4 w-4', md: 'h-6 w-6', lg: 'h-8 w-8' }
  const container = inline ? '' : 'flex flex-col items-center justify-center py-16'

  return (
    <div className={cn(container, className)} role="status" aria-label={text}>
      <svg
        className={cn('animate-spin text-[var(--color-brand-accent)]', sizes[size], !inline && 'mb-4')}
        fill="none"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3.5" />
        <path className="opacity-80" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      {!inline && <p className="text-sm text-[var(--color-text-tertiary)]" aria-hidden="true">{text}</p>}
    </div>
  )
}
