import { type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { PageHeader } from './page-header'
import { Skeleton } from './skeleton'
import { cn } from '../../lib/utils'

// ── Stat card (compact, enterprise-dense) ──────────────────────────

export interface HubStat {
  label: string
  value: number | string
  route?: string
  accent?: string
}

export function HubStatCard({ stat, loading }: { stat: HubStat; loading?: boolean }) {
  const navigate = useNavigate()
  return (
    <button
      onClick={() => stat.route && navigate(stat.route)}
      disabled={!stat.route}
      className={cn(
        'rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3.5 text-left',
        'motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)]',
        stat.route && 'hover:border-[var(--color-brand-accent)]/30 cursor-pointer',
        !stat.route && 'cursor-default',
      )}
    >
      <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)] truncate">
        {stat.label}
      </p>
      {loading ? (
        <Skeleton className="h-6 w-14 mt-1.5" />
      ) : (
        <p className={cn('mt-1.5 text-xl font-bold tabular-nums leading-none', stat.accent || 'text-[var(--color-text-primary)]')}>
          {typeof stat.value === 'number' ? stat.value.toLocaleString() : stat.value}
        </p>
      )}
    </button>
  )
}

// ── Quick link (compact row) ────────────────────────────────────────

export interface HubLink {
  label: string
  description: string
  route: string
  icon: string
}

export function HubLinkItem({ link }: { link: HubLink }) {
  const navigate = useNavigate()
  return (
    <button
      onClick={() => navigate(link.route)}
      className="flex items-center gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3.5 py-3 text-left w-full motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)] hover:border-[var(--color-brand-accent)]/30"
    >
      <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-[var(--color-bg)] flex-shrink-0">
        <svg className="h-4 w-4 text-[var(--color-text-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={link.icon} />
        </svg>
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-[var(--color-text-primary)] truncate">{link.label}</p>
        <p className="text-xs text-[var(--color-text-tertiary)] truncate">{link.description}</p>
      </div>
      <svg className="h-3.5 w-3.5 text-[var(--color-text-muted)] flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
      </svg>
    </button>
  )
}

// ── Section heading ──────────────────────────────────────────────────

export function HubSectionHeading({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <div>
        <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">{title}</h2>
        {subtitle && <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

// ── Full hub page layout ────────────────────────────────────────────

export interface HubPageProps {
  /** Page header eyebrow (section context) */
  eyebrow: string
  /** Page title */
  title: string
  /** Page subtitle (optional) */
  subtitle?: string
  /** Stats to show in the top row */
  stats: HubStat[]
  /** Quick links to sub-pages */
  links: HubLink[]
  /** Optional recent items content (table or list) */
  recentContent?: ReactNode
  /** Optional additional sections */
  children?: ReactNode
  /** Loading state */
  loading?: boolean
}

export function HubPage({
  eyebrow,
  title,
  subtitle,
  stats,
  links,
  recentContent,
  children,
  loading,
}: HubPageProps) {
  return (
    <div className="space-y-5 animate-fade-in">
      <PageHeader
        eyebrow={eyebrow}
        title={title}
        subtitle={subtitle}
        compact
      />

      {/* Stats row */}
      {stats.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
          {stats.map((stat) => (
            <HubStatCard key={stat.label} stat={stat} loading={loading} />
          ))}
        </div>
      )}

      {/* Main content area: links + recent items side by side on desktop */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Quick links (1/3 width on desktop) */}
        <div>
          <HubSectionHeading title="Quick Links" />
          <div className="space-y-2">
            {links.map((link) => (
              <HubLinkItem key={link.route} link={link} />
            ))}
          </div>
        </div>

        {/* Recent content (2/3 width on desktop) */}
        {recentContent && (
          <div className="lg:col-span-2">
            {recentContent}
          </div>
        )}
      </div>

      {/* Additional sections */}
      {children}
    </div>
  )
}
