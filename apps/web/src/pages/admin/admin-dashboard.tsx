import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminDashboardApi, type AdminOverview } from '../../api/admin/admin-api'
import { PageHeader, Badge, Skeleton } from '../../components/ui'
import { cn, plural } from '../../lib/utils'

// ── Metric card (compact, enterprise-dense) ──────────────────────────

function MetricCard({
  label,
  value,
  route,
  accent,
  loading,
}: {
  label: string
  value: number
  route?: string
  accent?: string
  loading?: boolean
}) {
  const navigate = useNavigate()
  return (
    <button
      onClick={() => route && navigate(route)}
      disabled={!route}
      className={cn(
        'rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-left',
        'motion-safe:transition-all motion-safe:duration-[var(--motion-fast)]',
        route && 'hover:border-[var(--color-brand-accent)]/30 hover:shadow-sm cursor-pointer',
        !route && 'cursor-default',
      )}
    >
      <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)] truncate">
        {label}
      </p>
      {loading ? (
        <Skeleton className="h-7 w-16 mt-2" />
      ) : (
        <p className={cn('mt-2 text-2xl font-bold tabular-nums leading-none', accent || 'text-[var(--color-text-primary)]')}>
          {value.toLocaleString()}
        </p>
      )}
    </button>
  )
}

// ── Section heading ──────────────────────────────────────────────────

function SectionHeading({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-3">
      <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">{title}</h2>
      {subtitle && <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">{subtitle}</p>}
    </div>
  )
}

// ── Role distribution bar ────────────────────────────────────────────

function RoleDistribution({ data, loading }: { data: Record<string, number> | null; loading: boolean }) {
  const navigate = useNavigate()
  const roles = [
    { key: 'admin', label: 'Admin', color: 'bg-[var(--color-brand-accent)]' },
    { key: 'principal', label: 'Principal', color: 'bg-indigo-500' },
    { key: 'accountant', label: 'Accountant', color: 'bg-blue-500' },
    { key: 'staff', label: 'Staff', color: 'bg-teal-500' },
    { key: 'teacher', label: 'Teacher', color: 'bg-emerald-500' },
    { key: 'student', label: 'Student', color: 'bg-violet-500' },
    { key: 'parent', label: 'Parent', color: 'bg-amber-500' },
  ]

  const total = data ? Object.values(data).reduce((a, b) => a + b, 0) : 0

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <SectionHeading title="Role Distribution" subtitle={total > 0 ? `${total} users total` : undefined} />
      {loading ? (
        <div className="space-y-2 mt-3">
          {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-5 w-full" />)}
        </div>
      ) : data ? (
        <div className="space-y-2 mt-3">
          {/* Visual bar */}
          <div className="flex h-2 rounded-full overflow-hidden bg-[var(--color-bg)]">
            {roles.map((r) => {
              const count = data[r.key] || 0
              const pct = total > 0 ? (count / total) * 100 : 0
              return pct > 0 ? (
                <div
                  key={r.key}
                  className={cn('h-full', r.color)}
                  style={{ width: `${pct}%` }}
                  title={`${r.label}: ${count}`}
                />
              ) : null
            })}
          </div>
          {/* Legend */}
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {roles.map((r) => {
              const count = data[r.key] || 0
              return (
                <button
                  key={r.key}
                  onClick={() => navigate(`/users?role=${r.key}`)}
                  className="flex items-center gap-1.5 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] motion-safe:transition-colors"
                >
                  <span className={cn('h-2 w-2 rounded-full', r.color)} aria-hidden="true" />
                  {r.label}
                  <span className="tabular-nums text-[var(--color-text-tertiary)]">{count}</span>
                </button>
              )
            })}
          </div>
        </div>
      ) : (
        <p className="text-xs text-[var(--color-text-tertiary)] mt-3">No user data available.</p>
      )}
    </div>
  )
}

// ── Quick actions ────────────────────────────────────────────────────

function QuickActions() {
  const navigate = useNavigate()
  const actions = [
    { label: 'Add User', route: '/users', icon: 'M12 4v16m8-8H4' },
    { label: 'Add Student', route: '/students', icon: 'M12 4v16m8-8H4' },
    { label: 'Audit Log', route: '/admin/audit-logs', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2' },
    { label: 'Data Migration', route: '/migration', icon: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15' },
  ]

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <SectionHeading title="Quick Actions" />
      <div className="grid grid-cols-2 gap-2 mt-3">
        {actions.map((a) => (
          <button
            key={a.route}
            onClick={() => navigate(a.route)}
            className="flex items-center gap-2.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2.5 text-left text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/30 hover:text-[var(--color-brand-accent)] motion-safe:transition-colors"
          >
            <svg className="h-4 w-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={a.icon} />
            </svg>
            {a.label}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── System status summary ────────────────────────────────────────────

function SystemStatus({ overview, loading }: { overview: AdminOverview | null; loading: boolean }) {
  const navigate = useNavigate()
  const items = [
    { label: 'Pending Leave', value: overview?.leave_requests?.total ?? 0, route: '/leave', accent: 'text-[var(--color-warning)]' },
    { label: 'Admissions', value: overview?.admissions?.total ?? 0, route: '/admissions/applications' },
    { label: 'Audit Events', value: overview?.audit_events?.total ?? 0, route: '/admin/audit-logs' },
    { label: 'Notifications', value: overview?.notifications?.total ?? 0, route: '/notifications' },
  ]

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <SectionHeading title="System Activity" />
      <div className="space-y-0 divide-y divide-[var(--color-divider)] mt-3">
        {items.map((item) => (
          <button
            key={item.label}
            onClick={() => navigate(item.route)}
            className="w-full flex items-center justify-between py-2.5 text-left group"
          >
            <span className="text-xs text-[var(--color-text-secondary)] group-hover:text-[var(--color-text-primary)] motion-safe:transition-colors">
              {item.label}
            </span>
            {loading ? (
              <Skeleton className="h-4 w-10" />
            ) : (
              <span className={cn('text-xs font-semibold tabular-nums', item.accent || 'text-[var(--color-text-primary)]')}>
                {item.value.toLocaleString()}
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Main page ────────────────────────────────────────────────────────

export function AdminDashboardPage() {
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [userCounts, setUserCounts] = useState<{ active: number; inactive: number; by_role: Record<string, number> } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  const load = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    try {
      const [ov, uc] = await Promise.all([
        adminDashboardApi.getOverview(),
        adminDashboardApi.getUserCounts(),
      ])
      if (fetchId === fetchIdRef.current) {
        setOverview(ov)
        setUserCounts(uc)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) {
        setError(err?.detail || 'Failed to load admin dashboard')
      }
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    return () => { fetchIdRef.current++ }
  }, [load])

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader
        eyebrow="Administration"
        title="System Dashboard"
        subtitle={overview ? `System-wide overview · ${new Date(overview.generated_at).toLocaleString()}` : 'System-wide overview'}
        compact
      />

      {error && (
        <div className="rounded-xl border border-[var(--color-danger)]/25 bg-[var(--color-danger)]/5 p-4 flex items-center gap-3">
          <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-[var(--color-danger)]/10 flex-shrink-0">
            <svg className="h-4 w-4 text-[var(--color-danger)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-[var(--color-danger-dark)]">{error}</p>
          </div>
          <button onClick={load} className="text-xs font-medium text-[var(--color-danger)] hover:underline">
            Retry
          </button>
        </div>
      )}

      {/* ── Users & People ── */}
      <section>
        <SectionHeading title="People & Access" subtitle="Users, students, and teaching staff" />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-3">
          <MetricCard label="Total Users" value={overview?.users?.total ?? 0} route="/users" loading={loading} />
          <MetricCard label="Active Users" value={userCounts?.active ?? 0} route="/users" loading={loading} accent="text-[var(--color-success)]" />
          <MetricCard label="Inactive" value={userCounts?.inactive ?? 0} route="/users" loading={loading} accent="text-[var(--color-text-tertiary)]" />
          <MetricCard label="Students" value={overview?.students?.total ?? 0} route="/students" loading={loading} />
          <MetricCard label="Teachers" value={overview?.teachers?.total ?? 0} route="/teachers" loading={loading} />
          <MetricCard label="Admissions" value={overview?.admissions?.total ?? 0} route="/admissions/applications" loading={loading} />
        </div>
      </section>

      {/* ── Academics ── */}
      <section>
        <SectionHeading title="Academics" subtitle="Classes, sections, and enrollment" />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mt-3">
          <MetricCard label="Classes" value={overview?.classes?.total ?? 0} route="/academic/classes" loading={loading} />
          <MetricCard label="Sections" value={overview?.sections?.total ?? 0} route="/academic/sections" loading={loading} />
          <MetricCard label="Enrollments" value={overview?.enrollments?.total ?? 0} route="/academic/enrollments" loading={loading} />
          <MetricCard label="Fee Types" value={overview?.fee_types?.total ?? 0} route="/fees/fee-types" loading={loading} />
        </div>
      </section>

      {/* ── Finance ── */}
      <section>
        <SectionHeading title="Finance" subtitle="Fee dues, payments, and collections" />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mt-3">
          <MetricCard label="Fee Dues" value={overview?.fee_dues?.total ?? 0} route="/fees/dues" loading={loading} />
          <MetricCard label="Payments" value={overview?.payments?.total ?? 0} route="/fees/payments" loading={loading} accent="text-[var(--color-success)]" />
          <MetricCard label="Attendance Records" value={overview?.attendance_records?.total ?? 0} route="/attendance/records" loading={loading} />
          <MetricCard label="Leave Requests" value={overview?.leave_requests?.total ?? 0} route="/leave" loading={loading} accent={(overview?.leave_requests?.total ?? 0) > 0 ? 'text-[var(--color-warning)]' : undefined} />
        </div>
      </section>

      {/* ── Two-column: Role distribution + System activity ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <RoleDistribution data={userCounts?.by_role ?? null} loading={loading} />
        <SystemStatus overview={overview} loading={loading} />
      </div>

      {/* ── Quick actions ── */}
      <QuickActions />
    </div>
  )
}

export default AdminDashboardPage
