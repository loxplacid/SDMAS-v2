import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { teacher360Api, type Teacher360Response } from '../../api/teacher-360/teacher-360-api'
import {
  Card, TabGroup, Badge, Button, Breadcrumbs, PageHeader, ErrorState,
} from '../../components/ui'
import { Timeline } from '../../components/timeline/timeline'
import { usePermission } from '../../hooks/use-permission'
import { formatDate } from '../../lib/utils'

const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  active: 'success',
  inactive: 'danger',
  on_leave: 'warning',
}

function MetricCard({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
      <div className="text-center">
        <p className={`text-2xl font-bold ${color || 'text-[var(--color-text-primary)]'}`}>{value}</p>
        <p className="text-xs text-[var(--color-text-tertiary)] mt-1">{label}</p>
      </div>
    </Card>
  )
}

// ── Tab: Overview ──────────────────────────────────────────────────────

function OverviewTab({ data }: { data: Teacher360Response }) {
  const navigate = useNavigate()
  const { profile: t, workload, attendance } = data
  return (
    <div className="space-y-6">
      {/* Hero Identity */}
      <Card className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-[var(--color-brand-accent)]/5 to-transparent pointer-events-none" />
        <div className="flex items-start gap-6 relative z-10">
          <div className="h-20 w-20 rounded-2xl bg-gradient-to-br from-[var(--color-brand-accent)] to-[var(--color-brand-accent-hover)] flex items-center justify-center text-white text-3xl font-bold shadow-lg shrink-0">
            {t.first_name[0]}{t.last_name[0]}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h2 className="text-2xl font-bold text-[var(--color-text-primary)]">{t.first_name} {t.last_name}</h2>
              <Badge variant={statusBadge[t.status] || 'default'}>{t.status}</Badge>
            </div>
            <p className="text-sm text-[var(--color-text-tertiary)] mt-1">
              Employee #{t.employee_number} {t.email ? `· ${t.email}` : ''}
            </p>
            <div className="flex gap-2 mt-4">
              <Button size="sm" onClick={() => navigate('/teachers')}>Teacher List</Button>
              <Button size="sm" variant="outline" onClick={() => navigate(`/teachers/${t.id}`)}>Full Profile</Button>
            </div>
          </div>
        </div>
      </Card>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Classes" value={workload.assigned_classes} />
        <MetricCard label="Subjects" value={workload.subjects} />
        <MetricCard label="Periods/Week" value={workload.timetable_periods} />
        <MetricCard label="Attendance" value={`${attendance.percentage}%`} color={attendance.percentage >= 75 ? 'text-green-600' : 'text-red-600'} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="Assigned Classes" subtitle="Drill down to class context">
          {data.assignments.length === 0 ? (
            <p className="text-sm text-[var(--color-text-tertiary)] py-4 text-center">No classes assigned</p>
          ) : (
            <div className="space-y-0 divide-y divide-[var(--color-border)]">
              {data.assignments.map((a) => (
                <button key={a.assignment_id} onClick={() => navigate('/academic/classes')}
                  className="w-full flex items-center justify-between py-3 text-left hover:bg-[var(--color-surface-hover)] px-2 rounded-md transition-colors">
                  <div className="min-w-0">
                    <p className="font-medium text-sm text-[var(--color-text-primary)]">{a.class_name}</p>
                    <p className="text-xs text-[var(--color-text-tertiary)]">
                      {[a.academic_year_name, a.section_name, a.subject_name].filter(Boolean).join(' · ')}
                    </p>
                  </div>
                  <span className="text-[var(--color-text-tertiary)] shrink-0">→</span>
                </button>
              ))}
            </div>
          )}
        </Card>

        <Card title="Subjects">
          {data.subjects.length === 0 ? (
            <p className="text-sm text-[var(--color-text-tertiary)] py-4 text-center">No subjects assigned</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {data.subjects.map((s) => (
                <button key={s.subject_id} onClick={() => navigate('/subjects')}
                  className="px-3 py-1.5 rounded-full bg-[var(--color-surface-hover)] text-sm font-medium text-[var(--color-text-primary)] hover:bg-[var(--color-brand-accent)]/10 transition-colors">
                  {s.subject_name} {s.code ? <span className="text-xs text-[var(--color-text-tertiary)]">({s.code})</span> : null}
                </button>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

// ── Tab: Attendance ────────────────────────────────────────────────────

function AttendanceTab({ data }: { data: Teacher360Response }) {
  const { attendance: att } = data
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <MetricCard label="Total" value={att.total} />
        <MetricCard label="Present" value={att.present} color="text-green-600" />
        <MetricCard label="Absent" value={att.absent} color="text-red-600" />
        <MetricCard label="Late" value={att.late} color="text-yellow-600" />
        <MetricCard label="Excused" value={att.excused} color="text-blue-600" />
      </div>

      <Card title="Attendance Rate" subtitle="Across classes this teacher teaches · last 90 days">
        <div className="flex items-center gap-4">
          <div className="relative h-24 w-24 shrink-0">
            <svg className="h-24 w-24 -rotate-90" viewBox="0 0 36 36">
              <circle cx="18" cy="18" r="15.5" fill="none" stroke="var(--color-border)" strokeWidth="3" />
              <circle cx="18" cy="18" r="15.5" fill="none"
                stroke={att.percentage >= 75 ? '#22c55e' : '#ef4444'}
                strokeWidth="3" strokeDasharray={`${att.percentage} ${100 - att.percentage}`}
                strokeLinecap="round" />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-lg font-bold text-[var(--color-text-primary)]">{att.percentage}%</span>
            </div>
          </div>
          <div className="text-sm text-[var(--color-text-tertiary)]">
            <p>{att.present} days present out of {att.total} total recorded</p>
            <p className="mt-1">Students across this teacher&apos;s assigned classes.</p>
          </div>
        </div>
      </Card>
    </div>
  )
}

// ── Tab: Leave ─────────────────────────────────────────────────────────

function LeaveTab({ data }: { data: Teacher360Response }) {
  return (
    <Card title="Leave History">
      {data.leave.length === 0 ? (
        <p className="text-sm text-[var(--color-text-tertiary)] py-8 text-center">No leave recorded</p>
      ) : (
        <div className="space-y-0 divide-y divide-[var(--color-border)]">
          {data.leave.map((l) => (
            <div key={l.id} className="flex items-center justify-between py-3">
              <div>
                <p className="font-medium text-sm text-[var(--color-text-primary)] capitalize">{l.leave_type}</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">
                  {l.start_date} → {l.end_date} · {l.duration_days} day(s)
                </p>
              </div>
              <Badge variant={l.status === 'approved' ? 'success' : l.status === 'rejected' ? 'danger' : 'warning'}>
                {l.status || 'pending'}
              </Badge>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

// ── Tab: Pending Workflows ─────────────────────────────────────────────

function WorkflowTab({ data }: { data: Teacher360Response }) {
  const items = data.pending_workflows
  return (
    <Card title="Pending Workflows">
      {items.length === 0 ? (
        <p className="text-sm text-[var(--color-text-tertiary)] py-8 text-center">No active workflows for this teacher</p>
      ) : (
        <div className="space-y-0 divide-y divide-[var(--color-border)]">
          {items.map((w) => (
            <div key={w.id} className="flex items-center justify-between py-3">
              <div>
                <p className="font-medium text-sm text-[var(--color-text-primary)]">{w.workflow_name}</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">
                  {w.current_step || w.status} · {formatDate(w.created_at)}
                </p>
              </div>
              <Badge variant="warning">{w.status}</Badge>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

// ── Tab: Recent Activity (unified operational timeline) ───────────────

function ActivityTab({ data }: { data: Teacher360Response }) {
  return (
    <div className="space-y-3">
      <div className="flex items-start gap-3 rounded-2xl border border-[var(--color-info)]/20 bg-[var(--color-info)]/5 p-4">
        <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-info)]/10 flex-shrink-0">
          <svg className="h-4.5 w-4.5 text-[var(--color-info)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <div>
          <p className="text-sm font-semibold text-[var(--color-text-primary)]">Recent Activity</p>
          <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">
            Unified activity — audit, approvals &amp; assignments for this teacher.
          </p>
        </div>
      </div>
      <Timeline params={{ entity_type: 'teacher', entity_id: data.profile.id }} compact />
    </div>
  )
}

// ── Main 360 Page ──────────────────────────────────────────────────────

const ALL_TABS = [
  { id: 'overview', label: 'Overview', permission: null },
  { id: 'attendance', label: 'Attendance', permission: null },
  { id: 'leave', label: 'Leave', permission: null },
  { id: 'workflow', label: 'Workflows', permission: null },
  { id: 'activity', label: 'Activity', permission: null },
]

export function Teacher360Page() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('overview')
  const [data, setData] = useState<Teacher360Response | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { can } = usePermission()

  const tabs = useMemo(
    () => ALL_TABS.filter((t) => !t.permission || can(t.permission)),
    [can],
  )

  useEffect(() => {
    if (!id) return
    setLoading(true)
    setError(null)
    teacher360Api.get(Number(id))
      .then(setData)
      .catch((err) => setError(err?.detail || 'Failed to load teacher 360 view'))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in-up">
        <div className="h-4 bg-[var(--color-border)] rounded w-64 animate-pulse" />
        <div className="h-8 bg-[var(--color-border)] rounded w-48 animate-pulse" />
        <div className="h-40 bg-[var(--color-surface)] rounded-xl animate-pulse" />
        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => <div key={i} className="h-24 bg-[var(--color-surface)] rounded-xl animate-pulse" />)}
        </div>
        <div className="h-64 bg-[var(--color-surface)] rounded-xl animate-pulse" />
      </div>
    )
  }

  if (error) {
    return <ErrorState message={error} onRetry={() => window.location.reload()} />
  }

  if (!data) {
    return <ErrorState message="Teacher not found" />
  }

  const t = data.profile

  return (
    <div className="space-y-6 animate-fade-in-up">
      <Breadcrumbs items={[
        { label: 'Teachers', href: '/teachers' },
        { label: `${t.first_name} ${t.last_name}`, href: `/teachers/${t.id}` },
        { label: '360 View' },
      ]} />

      <div className="flex items-center justify-between gap-4">
        <PageHeader
          title={`${t.first_name} ${t.last_name}`}
          subtitle={`Employee #${t.employee_number} - 360° Overview`}
          actions={<Badge variant={statusBadge[t.status] || 'default'}>{t.status}</Badge>}
        />
        <div className="flex gap-2 shrink-0">
          <Button variant="outline" size="sm" onClick={() => navigate(`/teachers/${t.id}`)}>
            Standard View
          </Button>
          <Button variant="outline" size="sm" onClick={() => navigate('/teachers')}>
            Back to List
          </Button>
        </div>
      </div>

      <TabGroup
        tabs={tabs.map(({ id, label }) => ({ id, label }))}
        activeTab={activeTab}
        onChange={setActiveTab}
        variant="underline"
        size="md"
      />

      <div className="mt-2">
        {activeTab === 'overview' && <OverviewTab data={data} />}
        {activeTab === 'attendance' && <AttendanceTab data={data} />}
        {activeTab === 'leave' && <LeaveTab data={data} />}
        {activeTab === 'workflow' && <WorkflowTab data={data} />}
        {activeTab === 'activity' && <ActivityTab data={data} />}
      </div>
    </div>
  )
}
