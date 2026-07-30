import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { leaveApi, type LeaveRequestDetailResponse } from '../../api/leave/leave-api'
import { Card, Button, ErrorState, Breadcrumbs, PageHeader, StatusBadge, Loading } from '../../components/ui'
import { formatDateTime } from '../../lib/utils'
import { capitalize } from '../../lib/utils'

export function LeaveDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [leave, setLeave] = useState<LeaveRequestDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = async () => {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const data = await leaveApi.getById(Number(id))
      setLeave(data)
    } catch (err: any) {
      setError(err?.detail || 'Failed to load leave request')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [id])

  if (loading) return <Loading />
  if (error) return <ErrorState message={error} onRetry={loadData} />
  if (!leave) return <ErrorState message="Leave request not found" />

  const getStatusVariant = (status: string | null): 'success' | 'warning' | 'danger' | 'info' | 'neutral' => {
    if (!status) return 'neutral'
    const map: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'neutral'> = {
      active: 'warning',
      completed: 'success',
      cancelled: 'danger',
    }
    return map[status] || 'neutral'
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <Breadcrumbs items={[
        { label: 'Leave', href: '/leave' },
        { label: `Leave #${leave.id}` },
      ]} />

      <PageHeader
        title={`${capitalize(leave.leave_type)} Leave`}
        subtitle={`${leave.duration_days} day${leave.duration_days !== 1 ? 's' : ''} — ${leave.start_date} to ${leave.end_date}`}
        actions={
          <div className="flex items-center gap-2">
            <StatusBadge
              status={leave.workflow_status || 'draft'}
              variant={getStatusVariant(leave.workflow_status)}
            />
          </div>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="Leave Details" className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)]">
          <dl className="space-y-3 text-sm">
            {[
              ['Leave Type', capitalize(leave.leave_type)],
              ['Start Date', leave.start_date],
              ['End Date', leave.end_date],
              ['Duration', `${leave.duration_days} day${leave.duration_days !== 1 ? 's' : ''}`],
              ['Reason', leave.reason || '-'],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between items-center">
                <dt className="text-[var(--color-text-muted)]">{label}</dt>
                <dd className="font-medium text-[var(--color-text-primary)] text-right">{value}</dd>
              </div>
            ))}
          </dl>
        </Card>

        <Card title="Workflow Status" className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)]">
          <dl className="space-y-3 text-sm">
            {[
              ['Status', leave.workflow_status ? capitalize(leave.workflow_status) : 'Draft'],
              ['Current Step', leave.workflow_current_step || 'Not started'],
              ['Instance ID', leave.workflow_instance_id?.toString() || '-'],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between items-center">
                <dt className="text-[var(--color-text-muted)]">{label}</dt>
                <dd className="font-medium text-[var(--color-text-primary)] text-right">{value}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </div>

      {/* Workflow Timeline */}
      {leave.workflow_status && (
        <Card title="Approval Pipeline">
          <div className="flex flex-wrap items-center gap-1.5 mt-2">
            {[
              { label: 'Submitted', active: leave.workflow_status === 'active' || leave.workflow_status === 'completed' },
              { label: 'Manager Approval', active: leave.workflow_status === 'active' || leave.workflow_status === 'completed' },
              { label: 'HR Approval', active: leave.workflow_status === 'active' || leave.workflow_status === 'completed' },
              { label: 'Approved', active: leave.workflow_status === 'completed' },
            ].map((step, i) => (
              <div key={step.label} className="flex items-center gap-1.5">
                <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium whitespace-nowrap ${
                  step.active
                    ? 'bg-[var(--color-brand-accent)] text-white'
                    : 'bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]'
                }`}>
                  {step.active && (
                    <svg className="h-3 w-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                  {step.label}
                </span>
                {i < 3 && (
                  <svg className="h-3.5 w-3.5 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="flex gap-3">
        <Button variant="outline" onClick={() => navigate('/leave')}>Back to List</Button>
      </div>
    </div>
  )
}

export default LeaveDetailPage
