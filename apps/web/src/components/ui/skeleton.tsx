import { cn } from '../../lib/utils'

interface SkeletonProps {
  className?: string
  variant?: 'text' | 'circular' | 'rectangular' | 'card'
  width?: string | number
  height?: string | number
  count?: number
}

export function Skeleton({
  className,
  variant = 'text',
  width,
  height,
  count = 1,
}: SkeletonProps) {
  const baseClass = 'animate-skeleton rounded-md bg-[var(--color-border)]'

  const variants = {
    text: 'h-4 w-full',
    circular: 'rounded-full',
    rectangular: 'rounded-lg',
    card: 'rounded-xl h-32 w-full',
  }

  const items = Array.from({ length: count }, (_, i) => (
    <div
      key={i}
      className={cn(baseClass, variants[variant], className)}
      style={{
        width: typeof width === 'number' ? `${width}px` : width,
        height: typeof height === 'number' ? `${height}px` : height,
      }}
      aria-hidden="true"
    />
  ))

  if (count > 1) {
    return <div className="space-y-3">{items}</div>
  }

  return items[0]
}

export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-3 p-4">
      {/* Header */}
      <div className="flex gap-4 pb-2 border-b border-[var(--color-border)]">
        {Array.from({ length: cols }, (_, i) => (
          <Skeleton key={`h-${i}`} className="h-4 flex-1" />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }, (_, rowIdx) => (
        <div key={rowIdx} className="flex gap-4">
          {Array.from({ length: cols }, (_, colIdx) => (
            <Skeleton key={`r${rowIdx}-c${colIdx}`} className="h-3.5 flex-1" />
          ))}
        </div>
      ))}
    </div>
  )
}

export function CardSkeleton() {
  return (
    <div className="rounded-xl border border-[var(--color-border)] p-6 space-y-4">
      <Skeleton className="h-5 w-1/3" />
      <Skeleton className="h-8 w-1/2" />
      <Skeleton className="h-3 w-2/3" />
    </div>
  )
}

export function PageSkeleton({ sections = 3 }: { sections?: number }) {
  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="space-y-3">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-80" />
      </div>
      {/* Sections */}
      {Array.from({ length: sections }, (_, i) => (
        <div key={i} className="rounded-2xl border border-[var(--color-border)] p-6 space-y-4">
          <Skeleton className="h-5 w-1/3" />
          <Skeleton className="h-24 w-full" />
          <div className="flex gap-4">
            <Skeleton className="h-3 flex-1" />
            <Skeleton className="h-3 flex-1" />
            <Skeleton className="h-3 flex-[0.5]" />
          </div>
        </div>
      ))}
    </div>
  )
}

export function FormSkeleton({ fields = 4 }: { fields?: number }) {
  return (
    <div className="space-y-5 animate-fade-in">
      <div className="space-y-3">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-3 w-64" />
      </div>
      {Array.from({ length: fields }, (_, i) => (
        <div key={i} className="space-y-1.5">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-10 w-full rounded-lg" />
        </div>
      ))}
      <div className="flex gap-3 pt-2">
        <Skeleton className="h-10 w-28 rounded-lg" />
        <Skeleton className="h-10 w-28 rounded-lg" />
      </div>
    </div>
  )
}

export function KPISkeleton() {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="rounded-xl border border-[var(--color-border)] p-4 space-y-2">
          <Skeleton className="h-3 w-2/3" />
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="h-2 w-1/3" />
        </div>
      ))}
    </div>
  )
}
