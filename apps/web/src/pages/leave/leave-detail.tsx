import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { leaveApi, type LeaveRequestDetailResponse } from '../../api/leave/leave-api'
import { workflowApi, type WorkflowInstanceDetail } from '../../api/workflow/workflow-api'
import { Card, Button, ErrorState, BreadcrumbBar, PageHeader, StatusBadge, Loading } from '../../components/ui'
import { WorkflowStatus } from '../../components/workflow/workflow-status'
import { formatDateTime } from '../../lib/utils'
import { capitalize } from '../../lib/utils'

export function LeaveDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [leave, setLeave] = useState<LeaveRequestDetailResponse | null>(null)
  const [workflow, setWorkflow] = useState<WorkflowInstanceDetail | null>(null)
  const [workflowLoading, setWorkflowLoading] = useState(false)
  const [workflowError, setWorkflowError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = async () => {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const data = await leaveApi.getById(Number(id))
      setLeave(data)

      // Fetch the *real* workflow instance (P14 §6) — the leave detail only
      // carries its instance id; the full steps/current-step/history live on
      // the workflow engine.  Render nothing fake when there is no instance.
      if (data.workflow_instance_id) {
        setWorkflowLoading(true)
        setWorkflowError(null)
        try {
          const instance = await workflowApi.getInstance(data.workflow_instance_id)
          setWorkflow(instance)
        } catch (wfErr: any) {
          setWorkflowError(wfErr?.detail || 'Could not load approval progress')
        } finally {
          setWorkflowLoading(false)
        }
      } else {
        setWorkflow(null)
      }
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
      <BreadcrumbBar pageLabel={`Leave #${leave.id}`} />

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

      {/* Workflow progress — the real workflow definition, not a hardcoded pipeline */}
      {leave.workflow_instance_id ? (
        <Card title="Approval Pipeline">
          {workflowLoading ? (
            <div className="space-y-3 py-2">
              <div className="h-4 w-2/3 rounded bg-[var(--color-surface-hover)] motion-safe:animate-pulse" />
              <div className="h-4 w-1/2 rounded bg-[var(--color-surface-hover)] motion-safe:animate-pulse" />
              <div className="h-4 w-3/4 rounded bg-[var(--color-surface-hover)] motion-safe:animate-pulse" />
            </div>
          ) : workflowError ? (
            <p className="text-sm text-[var(--color-text-tertiary)] py-2">
              {workflowError}
            </p>
          ) : workflow ? (
            <WorkflowStatus instance={workflow} />
          ) : null}
        </Card>
      ) : leave.workflow_status ? (
        <Card title="Approval Pipeline">
          <p className="text-sm text-[var(--color-text-tertiary)] py-2">
            This request has workflow status “{capitalize(leave.workflow_status)}” but no
            workflow instance is attached. Contact an administrator if this looks wrong.
          </p>
        </Card>
      ) : null}

      <div className="flex gap-3">
        <Button variant="outline" onClick={() => navigate('/leave')}>Back to List</Button>
      </div>
    </div>
  )
}

export default LeaveDetailPage
