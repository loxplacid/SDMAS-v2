import { useMemo } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { cn } from '../../lib/utils'
import { getPageHierarchy, type PageCrumb } from '../../lib/nav/page-context'

interface BreadcrumbBarProps {
  /**
   * `header` — compact chrome variant (inside the app header, no margin,
   * no entrance stagger). `page` — block variant above page content with
   * margin + reading-order stagger (default).
   */
  variant?: 'header' | 'page'
  /** Full custom trail. When omitted, the route hierarchy (getPageHierarchy) is used. */
  items?: PageCrumb[]
  /** Override the trailing (page) crumb label of the derived trail. */
  pageLabel?: string
  /** Extra crumbs appended after the derived trail (e.g. `['360 View']`). */
  append?: PageCrumb[]
  className?: string
}

/**
 * BreadcrumbBar — the single breadcrumb surface for the shell.
 *
 * Both the app header (P8 §7) and pages render through this component, so
 * the trail is always derived from the same `getPageHierarchy` registry —
 * one source of truth. Detail pages override the page label (entity names)
 * via `pageLabel`; the 360 views keep their richer trails via `items`.
 */
export function BreadcrumbBar({
  variant = 'page',
  items,
  pageLabel,
  append,
  className,
}: BreadcrumbBarProps) {
  const location = useLocation()

  const crumbs = useMemo<PageCrumb[]>(() => {
    if (items) return items
    const trail = getPageHierarchy(location.pathname)
    if (pageLabel && trail.length > 0) {
      trail[trail.length - 1] = { ...trail[trail.length - 1], label: pageLabel }
    }
    if (append && append.length > 0) trail.push(...append)
    return trail
  }, [items, location.pathname, pageLabel, append])

  if (crumbs.length === 0) return null

  return (
    <nav
      aria-label="Breadcrumb"
      className={cn(
        variant === 'page' && 'mb-4 animate-fade-in',
        className
      )}
    >
      <ol
        className={cn(
          'flex items-center gap-1.5 text-[var(--color-text-tertiary)]',
          variant === 'header' ? 'text-xs' : 'text-sm'
        )}
      >
        {crumbs.map((crumb, idx) => {
          const isLast = idx === crumbs.length - 1
          return (
            <li
              key={`${crumb.label}-${idx}`}
              className={cn(
                'flex items-center gap-1.5 min-w-0',
                variant === 'page' && 'animate-fade-in'
              )}
              style={
                variant === 'page'
                  ? { animationDelay: `${idx * 50}ms`, animationFillMode: 'both' }
                  : undefined
              }
            >
              {idx > 0 && (
                <svg
                  className="h-3.5 w-3.5 flex-shrink-0 text-[var(--color-text-tertiary)]"
                  fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              )}
              {!isLast && crumb.href ? (
                <Link
                  to={crumb.href}
                  className={cn(
                    'hover:text-[var(--color-text-primary)] motion-safe:transition-colors',
                    variant === 'header' && 'whitespace-nowrap'
                  )}
                >
                  {crumb.label}
                </Link>
              ) : (
                <span
                  className={cn(
                    'truncate',
                    isLast
                      ? 'font-semibold text-[var(--color-text-primary)]'
                      : 'text-[var(--color-text-tertiary)]',
                    variant === 'header' && 'whitespace-nowrap'
                  )}
                  aria-current={isLast ? 'page' : undefined}
                >
                  {crumb.label}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
