import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'
import { MotionReveal } from '../../lib/motion'
import type { MoveSpec } from '../../lib/motion'

/**
 * PageHeader entrance (P7 §7): the page title area settles with a short,
 * grounded 8px rise + fade at `fast` (120ms, I1). Rendered by ~every page,
 * this is the shared "page frame" choreography — transform/opacity only,
 * no layout shift, and the tier system folds it to opacity-only (≤75ms) or
 * instant under reduced motion.
 */
const PAGE_HEADER_SPEC: MoveSpec = { verb: 'slide', direction: 'S', distance: 'D4', importance: 'I1' }

interface PageHeaderProps {
  title: string
  subtitle?: string
  /** P16 — section/context eyebrow above the title (e.g. "Academics", "Fees").
   *  Consolidates the hand-rolled context labels found across the app onto
   *  the one shared page header. */
  eyebrow?: string
  actions?: ReactNode
  className?: string
  compact?: boolean
}

export function PageHeader({ title, subtitle, eyebrow, actions, className, compact = false }: PageHeaderProps) {
  return (
    <MotionReveal
      spec={PAGE_HEADER_SPEC}
      className={cn(
        'flex flex-col sm:flex-row sm:items-center justify-between gap-3',
        compact ? 'mb-5' : 'mb-8',
        className
      )}
    >
      <div className="min-w-0 flex-1">
        {eyebrow && (
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand-accent)] mb-1">
            {eyebrow}
          </p>
        )}
        <h1 className="text-xl sm:text-2xl font-bold text-[var(--color-text-primary)] tracking-tight">
          {title}
        </h1>
        {subtitle && (
          <p className="text-sm text-[var(--color-text-muted)] mt-1">{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
    </MotionReveal>
  )
}
