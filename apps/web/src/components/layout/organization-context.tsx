import { useAuth } from '../../api/auth/auth-context'
import { useCampus } from '../../hooks/use-campus'
import { ROLE_BADGE_COLORS } from '../../types/roles'
import { Skeleton } from '../ui/skeleton'
import { Tooltip } from '../ui/tooltip'
import { cn, capitalize } from '../../lib/utils'

function OrgMark() {
  return (
    <span className="flex items-center justify-center h-6 w-6 rounded-md bg-[var(--color-brand-accent)]/15 text-[var(--color-brand-accent)] flex-shrink-0" aria-hidden="true">
      <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 21h18M5 21V7a2 2 0 012-2h10a2 2 0 012 2v14M9 7h6m-6 4h6m-6 4h6m-6 4h6" />
      </svg>
    </span>
  )
}

/**
 * D1 §1 — always-visible organization context.
 *
 * The current institution/campus identity is a persistent part of the
 * enterprise shell, not something buried in a menu. It renders the real
 * campus name (fetched from `GET /api/institution/campuses/{id}` via
 * `useCampus`, cached) next to the user's role badge. Purely informational —
 * tenant switching is backend-authoritative and admin-only via the
 * WorkspaceSwitcher; this chip never fakes a multi-org list.
 */
export function OrganizationContext() {
  const { user } = useAuth()
  const { campusName, isLoading } = useCampus()

  const content = (
    <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
      <OrgMark />
      <div className="min-w-0">
        <p className="text-[9px] font-semibold uppercase tracking-widest text-[var(--color-text-tertiary)] leading-tight">
          Organization
        </p>
        {isLoading ? (
          <Skeleton className="h-3.5 w-24 mt-0.5" />
        ) : (
          <p className="text-xs font-semibold text-[var(--color-text-primary)] leading-tight truncate max-w-[140px]">
            {campusName || '—'}
          </p>
        )}
      </div>
      {user?.role && (
        <span
          className={cn(
            'inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase tracking-widest flex-shrink-0',
            ROLE_BADGE_COLORS[user.role] || 'bg-[var(--color-surface-hover)] text-[var(--color-text-tertiary)]',
          )}
        >
          {capitalize(user.role)}
        </span>
      )}
    </div>
  )

  return (
    <Tooltip content={campusName || 'Organization'} position="bottom">
      {content}
    </Tooltip>
  )
}
