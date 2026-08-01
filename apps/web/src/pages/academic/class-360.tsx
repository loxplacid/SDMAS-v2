import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { class360Api, type Class360Response } from '../../api/class-360/class-360-api'
import {
  Card, TabGroup, Badge, Button, Breadcrumbs, PageHeader, ErrorState,
} from '../../components/ui'
import { Timeline } from '../../components/timeline/timeline'
import { Can } from '../../components/auth/can'
import { usePermission } from '../../hooks/use-permission'
import { FEES_VIEW } from '../../types/permissions'
import { formatDate } from '../../lib/utils'

const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  active: 'success',
  inactive: 'danger',
  archived: 'info',
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

function OverviewTab({ data }: { data: Class360Response }) {
  const navigate = useNavigate()
  const { identity: c, attendance: att, fees, sections } = data
  return (
    <div className="space-y-6">
      {/* Hero Identity */}
      <Card className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-[var(--color-brand-accent)]/5 to-transparent pointer-events-none" />
        <div className="flex items-start gap-6 relative z-10">
          <div className="h-20 w-20 rounded-2xl bg-gradient-to-br from-[var(--color-brand-accent)] to-[var(--color-brand-accent-hover)] flex items-center justify-center text-white text-3xl font-bold shadow-lg shrink-0">
            {c.name[0] || 'C'}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h2 className="text-2xl font-bold text-[var(--color-text-primary)]">{c.name}</h2>
              <Badge variant={statusBadge[c.status] || 'default'}>{c.status}</Badge>
            </div>
            <p className="text-sm text-[var(--color-text-tertiary)] mt-1">
              {c.academic_year_name ? `Academic Year: ${c.academic_year_name}` : 'No academic year'}
            </p>
            <div className="flex gap-2 mt-4">
              <Button size="sm" onClick={() => navigate('/academic/classes')}>Class List</Button>
              <Button size="sm" variant="outline" onClick={() => navigate(`/academic/enrollments?classId=${c.id}`)}>
                Enrollments
              </Button>
            </div>
          </div>
        </div>
      </Card>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Students" value={data.student_count} />
        <MetricCard label="Sections" value={sections.length} />
        <MetricCard label="Attendance" value={`${att.percentage}%`} color={att.percentage >= 75 ? 'text-green-600' : 'text-red-600'} />
        <MetricCard label="Outstanding" value={`$${fees.total_outstanding.toLocaleString()}`}
          color={fees.total_outstanding > 0 ? 'text-red-600' : 'text-green-600'} />
      </div>

      {/* Sections + Teachers + Subjects */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="Sections" subtitle="Drill down to students">
          {sections.length === 0 ? (
            <p className="text-sm text-[var(--color-text-tertiary)] py-4 text-center">No sections</p>
          ) : (
            <div className="space-y-0 divide-y divide-[var(--color-border)]">
              {sections.map((s) => (
                <button key={s.id} onClick={() => navigate(`/academic/enrollments?sectionId=${s.id}`)}
                  className="w-full flex items-center justify-between py-3 text-left hover:bg-[var(--color-surface-hover)] px-2 rounded-md transition-colors">
                  <div>
                    <p className="font-medium text-sm text-[var(--color-text-primary)]">{s.name}</p>
                    <p className="text-xs text-[var(--color-text-tertiary)] capitalize">{s.status}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="neutral">{s.student_count} students</Badge>
                    <span className="text-[var(--color-text-tertiary)]">→</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </Card>

        <Card title="Teachers">
          {data.teachers.length === 0 ? (
            <p className="text-sm text-[var(--color-text-tertiary)] py-4 text-center">No teachers assigned</p>
          ) : (
            <div className="space-y-0 divide-y divide-[var(--color-border)]">
              {data.teachers.map((t) => (
                <button key={t.teacher_id} onClick={() => navigate(`/teachers/${t.teacher_id}`)}
                  className="w-full flex items-center justify-between py-3 text-left hover:bg-[var(--color-surface-hover)] px-2 rounded-md transition-colors">
                  <span className="font-medium text-sm text-[var(--color-text-primary)]">{t.teacher_name}</span>
                  <span className="text-xs text-[var(--color-text-tertiary)]">{t.subject_name || 'Class Teacher'}</span>
                </button>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Subjects */}
      <Card title="Subjects">
        {data.subjects.length === 0 ? (
          <p className="text-sm text-[var(--color-text-tertiary)] py-4 text-center">No subjects assigned</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {data.subjects.map((s) => (
              <button key={s.id} onClick={() => navigate('/subjects')}
                className="px-3 py-1.5 rounded-full bg-[var(--color-surface-hover)] text-sm font-medium text-[var(--color-text-primary)] hover:bg-[var(--color-brand-accent)]/10 transition-colors">
                {s.name} {s.code ? <span className="text-xs text-[var(--color-text-tertiary)]">({s.code})</span> : null}
              </button>
            ))}
          </div>
        )}
      </Card>

      {/* Fees */}
      <Can permission={FEES_VIEW} fallback={
        <Card><div className="py-8 text-center text-sm text-[var(--color-text-tertiary)]">You do not have permission to view financial data.</div></Card>
      }>
        <Card title="Fee Collection">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard label="Assigned" value={`$${fees.total_assigned.toLocaleString()}`} />
            <MetricCard label="Collected" value={`$${fees.total_collected.toLocaleString()}`} color="text-green-600" />
            <MetricCard label="Outstanding" value={`$${fees.total_outstanding.toLocaleString()}`}
              color={fees.total_outstanding > 0 ? 'text-red-600' : 'text-green-600'} />
            <MetricCard label="With Dues" value={fees.students_with_outstanding} />
          </div>
        </Card>
      </Can>
    </div>
  )
}

// ── Tab: Requires Attention ────────────────────────────────────────────

function AttentionTab({ data }: { data: Class360Response }) {
  const navigate = useNavigate()
  const items = data.students_requiring_attention
  return (
    <Card title="Students Requiring Attention" subtitle="Low attendance or outstanding fees — drill down to Student 360">
      {items.length === 0 ? (
        <div className="py-10 text-center">
          <div className="flex items-center justify-center h-12 w-12 rounded-full bg-[var(--color-surface-hover)] mx-auto mb-3">
            <svg className="h-6 w-6 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p className="text-sm text-[var(--color-text-tertiary)]">All students look healthy — nothing needs attention.</p>
        </div>
      ) : (
        <div className="space-y-0 divide-y divide-[var(--color-border)]">
          {items.map((a) => (
            <button key={a.student_id} onClick={() => navigate(`/students/${a.student_id}/360`)}
              className="w-full flex items-center justify-between py-3 text-left hover:bg-[var(--color-surface-hover)] px-2 rounded-md transition-colors">
              <div className="min-w-0">
                <p className="font-medium text-sm text-[var(--color-text-primary)]">{a.full_name}</p>
                <p className="text-xs text-[var(--color-text-tertiary)]">#{a.student_number} · {a.reason}</p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                {a.attendance_percentage > 0 && (
                  <Badge variant={a.attendance_percentage >= 75 ? 'success' : 'danger'}>
                    {a.attendance_percentage}%
                  </Badge>
                )}
                {a.outstanding > 0 && (
                  <Badge variant="warning">${a.outstanding.toLocaleString()}</Badge>
                )}
                <span className="text-[var(--color-text-tertiary)]">→</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </Card>
  )
}

// ── Tab: Academic Performance ──────────────────────────────────────────

function PerformanceTab({ data }: { data: Class360Response }) {
  const items = data.academic_performance
  return (
    <Card title="Academic Performance" subtitle="Average percentage by subject">
      {items.length === 0 ? (
        <p className="text-sm text-[var(--color-text-tertiary)] py-8 text-center">No grade records available</p>
      ) : (
        <div className="space-y-4">
          {items.map((p) => (
            <div key={p.subject_id}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-[var(--color-text-primary)]">{p.subject_name}</span>
                <span className="text-xs text-[var(--color-text-tertiary)]">
                  {p.records} records · <span className={p.average_percentage >= 60 ? 'text-green-600' : 'text-red-600'}>{p.average_percentage}%</span>
                </span>
              </div>
              <div className="h-2 rounded-full bg-[var(--color-border)] overflow-hidden">
                <div className="h-full rounded-full bg-gradient-to-r from-[var(--color-brand-accent)] to-[var(--color-brand-accent-hover)] transition-all"
                  style={{ width: `${Math.min(p.average_percentage, 100)}%` }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

// ── Tab: Pending Workflows ─────────────────────────────────────────────

function WorkflowTab({ data }: { data: Class360Response }) {
  const items = data.pending_workflows
  return (
    <Card title="Pending Workflows">
      {items.length === 0 ? (
        <p className="text-sm text-[var(--color-text-tertiary)] py-8 text-center">No active workflows for this class</p>
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

function ActivityTab({ data }: { data: Class360Response }) {
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
            Unified activity — enrollments, audit &amp; approvals for this class.
          </p>
        </div>
      </div>
      <Timeline params={{ entity_type: 'class', entity_id: data.identity.id }} compact />
    </div>
  )
}

// ── Main 360 Page ──────────────────────────────────────────────────────

const ALL_TABS = [
  { id: 'overview', label: 'Overview', permission: null },
  { id: 'attention', label: 'Attention', permission: null },
  { id: 'performance', label: 'Performance', permission: null },
  { id: 'workflow', label: 'Workflows', permission: null },
  { id: 'activity', label: 'Activity', permission: null },
]

export function Class360Page() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('overview')
  const [data, setData] = useState<Class360Response | null>(null)
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
    class360Api.get(Number(id))
      .then(setData)
      .catch((err) => setError(err?.detail || 'Failed to load class 360 view'))
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
    return <ErrorState message="Class not found" />
  }

  const c = data.identity

  return (
    <div className="space-y-6 animate-fade-in-up">
      <Breadcrumbs items={[
        { label: 'Academic', href: '/academic' },
        { label: 'Classes', href: '/academic/classes' },
        { label: `${c.name}`, href: `/academic/classes/${c.id}` },
        { label: '360 View' },
      ]} />

      <div className="flex items-center justify-between gap-4">
        <PageHeader
          title={c.name}
          subtitle={`Class 360° Overview · ${data.student_count} students`}
          actions={<Badge variant={statusBadge[c.status] || 'default'}>{c.status}</Badge>}
        />
        <div className="flex gap-2 shrink-0">
          <Button variant="outline" size="sm" onClick={() => navigate('/academic/classes')}>
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
        {activeTab === 'attention' && <AttentionTab data={data} />}
        {activeTab === 'performance' && <PerformanceTab data={data} />}
        {activeTab === 'workflow' && <WorkflowTab data={data} />}
        {activeTab === 'activity' && <ActivityTab data={data} />}
      </div>
    </div>
  )
}
