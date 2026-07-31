import { useState, useEffect, useCallback, useRef } from 'react'
import { workflowApi, type WorkflowInstanceResponse, type WorkflowInstanceDetail, type AvailableTransition, type ApprovalHistoryEntry, type WorkflowResponse } from '../../api/workflow/workflow-api'
import { cn, capitalize, formatDateTime } from '../../lib/utils'
import { TabGroup, Button, Pagination, Select, EmptyState, ErrorState, Badge, Alert, ConfirmDialog, useToast, Card, Skeleton } from '../../components/ui'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'

// ── Helpers ──

const STATUS_LABELS: Record<string, string> = {
  active: 'Pending',
  completed: 'Approved',
  cancelled: 'Rejected',
}

const STATUS_BADGE_VARIANT: Record<string, 'info' | 'success' | 'danger' | 'warning' | 'neutral'> = {
  active: 'info',
  completed: 'success',
  cancelled: 'danger',
}

const ACTION_VARIANTS: Record<string, 'success' | 'danger' | 'warning' | 'info'> = {
  submit: 'info',
  approve: 'success',
  reject: 'danger',
  return: 'warning',
}

const ENTITY_TYPE_LABELS: Record<string, string> = {
  leave_request: 'Leave Request',
  fee_adjustment: 'Fee Adjustment',
  student_transfer: 'Student Transfer',
  document: 'Document',
  rollover: 'Rollover',
  disciplinary: 'Disciplinary',
}

function getEntityLabel(entityType: string): string {
  return ENTITY_TYPE_LABELS[entityType] || capitalize(entityType.replace(/_/g, ' '))
}

function getEntityUrl(entityType: string, entityId: number): string {
  const map: Record<string, string> = {
    leave_request: `/leave/${entityId}`,
    fee_adjustment: `/fees/dues`,
    student_transfer: `/students/${entityId}`,
    rollover: `/operations/rollover`,
  }
  return map[entityType] || '#'
}

function getActorLabel(entry: ApprovalHistoryEntry): string {
  return entry.actor_id ? `User #${entry.actor_id}` : 'System'
}

// ── Page Component ──

export function ApprovalInboxPage() {
  const { showToast } = useToast()

  // ── List state ──
  const [instances, setInstances] = useState<WorkflowInstanceResponse[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1)
  const size = 20
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<string>('active')
  const [entityFilter, setEntityFilter] = useState('')

  // ── Detail / Action state ──
  const [detailLoading, setDetailLoading] = useState(false)
  const [selectedInstance, setSelectedInstance] = useState<WorkflowInstanceDetail | null>(null)
  const [availableTransitions, setAvailableTransitions] = useState<AvailableTransition[]>([])
  const [detailOpen, setDetailOpen] = useState(false)
  const [actionComment, setActionComment] = useState('')
  const [actionLoading, setActionLoading] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [confirmAction, setConfirmAction] = useState<string | null>(null)
  const [showHistory, setShowHistory] = useState(false)

  // Prevent stale fetch
  const fetchIdRef = useRef(0)

  // ── Keyboard shortcuts ──
  useKeyboardShortcut({
    'r': () => fetchInstances(),
  }, [tab, entityFilter, page])

  // ── Fetch instances ──
  const fetchInstances = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    try {
      const result = await workflowApi.listInstances({
        status: tab === 'all' ? undefined : tab,
        entity_type: entityFilter || undefined,
        page,
        size,
      })
      if (fetchId === fetchIdRef.current) {
        setInstances(result.items)
        setTotal(result.total)
        setPages(result.pages)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) {
        setError(err?.detail || 'Failed to load approval queue')
      }
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [tab, entityFilter, page])

  useEffect(() => {
    fetchInstances()
  }, [fetchInstances])

  // ── Open detail panel ──
  async function openDetail(instance: WorkflowInstanceResponse) {
    setDetailLoading(true)
    setDetailOpen(true)
    setSelectedInstance(null)
    setActionComment('')
    setActionError(null)
    setShowHistory(false)

    try {
      const [detail, transitions] = await Promise.all([
        workflowApi.getInstance(instance.id),
        workflowApi.getAvailableTransitions(instance.id),
      ])
      setSelectedInstance(detail)
      setAvailableTransitions(transitions)
    } catch (err: any) {
      setActionError(err?.detail || 'Failed to load instance detail')
    } finally {
      setDetailLoading(false)
    }
  }

  function closeDetail() {
    setDetailOpen(false)
    setSelectedInstance(null)
    setAvailableTransitions([])
    setActionComment('')
    setActionError(null)
    setConfirmAction(null)
  }

  // ── Perform action ──
  async function handleAction(action: string) {
    if (!selectedInstance) return
    setConfirmAction(null)
    setActionLoading(true)
    setActionError(null)

    try {
      const transition = availableTransitions.find((t) => {
        if (action === 'return') return t.label?.toLowerCase().includes('return')
        if (action === 'reject') return t.label?.toLowerCase() === 'reject'
        return t.label?.toLowerCase() === action
      })

      const result = await workflowApi.performAction(selectedInstance.id, {
        action: action as 'approve' | 'reject' | 'return' | 'submit',
        comment: actionComment || null,
        to_step_id: transition?.to_step_id || null,
      })

      showToast(
        action === 'approve' ? 'Approved successfully' :
        action === 'reject' ? 'Rejected' :
        action === 'return' ? 'Returned for revision' :
        'Action completed',
        'success'
      )

      // Refresh list and detail
      closeDetail()
      fetchInstances()
    } catch (err: any) {
      setActionError(err?.detail || `Failed to ${action}`)
    } finally {
      setActionLoading(false)
    }
  }

  const tabs = [
    { id: 'active', label: 'Pending' },
    { id: 'completed', label: 'Approved' },
    { id: 'cancelled', label: 'Rejected' },
  ]

  const entityOptions = Object.entries(ENTITY_TYPE_LABELS).map(([value, label]) => ({ value, label }))

  // ── Render ──
  return (
    <div className="animate-fade-in-up">
      {/* Header */}
      <div className="mb-8">
        <p className="text-sm font-medium text-[var(--color-brand-accent)] tracking-wide mb-1">Workflows</p>
        <h1 className="text-3xl lg:text-4xl font-extrabold text-[var(--color-text-primary)] tracking-tight leading-tight">
          Approval Inbox
        </h1>
        <p className="text-base text-[var(--color-text-tertiary)] mt-2 max-w-xl">
          {total > 0
            ? `${total} workflow instance${total !== 1 ? 's' : ''} requiring attention`
            : 'Track and manage approval requests across your school.'}
        </p>
      </div>

      {/* Tabs + Filters */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <TabGroup
          tabs={tabs}
          activeTab={tab}
          onChange={(id) => { setTab(id); setPage(1) }}
          variant="pills"
          size="sm"
        />
        <div className="flex items-center gap-3">
          <Select
            options={entityOptions}
            placeholder="All types"
            value={entityFilter}
            onChange={(e) => { setEntityFilter(e.target.value); setPage(1) }}
            className="min-w-[160px]"
          />
          <Button variant="ghost" size="sm" onClick={fetchInstances}>
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </Button>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-20 w-full rounded-xl" />
          ))}
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={fetchInstances} />
      ) : instances.length === 0 ? (
        <EmptyState
          title={tab === 'active' ? 'No pending approvals' : tab === 'completed' ? 'No approved items' : 'No rejected items'}
          description={
            entityFilter
              ? `No ${STATUS_LABELS[tab]?.toLowerCase() || ''} ${getEntityLabel(entityFilter).toLowerCase()} workflows found`
              : `All caught up! No ${STATUS_LABELS[tab]?.toLowerCase() || ''} workflow instances.`
          }
          icon={
            <svg className="h-12 w-12" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />
      ) : (
        <>
          {/* Instance list */}
          <div className="space-y-2" role="list" aria-label="Approval instances">
            {instances.map((instance) => (
              <button
                key={instance.id}
                onClick={() => openDetail(instance)}
                className={cn(
                  'w-full text-left flex items-start gap-4 p-4 rounded-xl border motion-safe:transition-all motion-safe:duration-150',
                  'bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)] border-[var(--color-border)]',
                  'focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-accent)] focus:ring-offset-2',
                  instance.status === 'active' && 'border-l-[3px] border-l-[var(--color-brand-accent)]'
                )}
                role="listitem"
              >
                {/* Status indicator */}
                <div className={cn(
                  'flex-shrink-0 h-10 w-10 rounded-xl flex items-center justify-center',
                  instance.status === 'active' ? 'bg-[var(--color-brand-accent-subtle)]' :
                  instance.status === 'completed' ? 'bg-emerald-50 dark:bg-emerald-900/20' :
                  'bg-red-50 dark:bg-red-900/20'
                )}>
                  {instance.status === 'active' ? (
                    <svg className="h-5 w-5 text-[var(--color-brand-accent)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  ) : instance.status === 'completed' ? (
                    <svg className="h-5 w-5 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  ) : (
                    <svg className="h-5 w-5 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-[var(--color-text-primary)]">
                        {getEntityLabel(instance.entity_type)} #{instance.entity_id}
                      </p>
                      <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">
                        Created {formatDateTime(instance.created_at)}
                        {instance.created_by && ` by User #${instance.created_by}`}
                      </p>
                    </div>
                    <Badge
                      variant={STATUS_BADGE_VARIANT[instance.status] || 'neutral'}
                      size="sm"
                    >
                      {STATUS_LABELS[instance.status] || capitalize(instance.status)}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-3 mt-2">
                    <span className="text-[11px] text-[var(--color-text-muted)]">
                      Workflow #{instance.workflow_id}
                    </span>
                    <span className="text-[11px] text-[var(--color-text-muted)]">
                      {getEntityLabel(instance.entity_type)}
                    </span>
                  </div>
                </div>

                {/* Chevron */}
                <svg className="h-5 w-5 flex-shrink-0 text-[var(--color-text-muted)] mt-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            ))}
          </div>

          {/* Pagination */}
          {pages > 1 && (
            <div className="mt-6 pt-4 border-t border-[var(--color-divider)]">
              <Pagination
                page={page}
                size={size}
                total={total}
                pages={pages}
                onPageChange={setPage}
              />
            </div>
          )}
        </>
      )}

      {/* ── Detail Drawer ── */}
      {detailOpen && (
        <div className="fixed inset-0 z-50 flex justify-end">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/30 backdrop-blur-sm motion-safe:animate-fade-in"
            onClick={closeDetail}
            aria-hidden="true"
          />
          {/* Panel */}
          <div
            className={cn(
              'relative w-full max-w-lg bg-[var(--color-surface)] h-full overflow-y-auto',
              'shadow-2xl border-l border-[var(--color-border)] motion-safe:animate-slide-in-right'
            )}
          >
            {/* Header */}
            <div className="sticky top-0 z-10 bg-[var(--color-surface)] border-b border-[var(--color-border)] px-6 py-4 flex items-center justify-between">
              <h2 className="text-lg font-bold text-[var(--color-text-primary)]">
                Instance Details
              </h2>
              <button
                onClick={closeDetail}
                className="p-2 rounded-lg text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-hover)] transition-colors"
                aria-label="Close detail"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Content */}
            <div className="px-6 py-5 space-y-6">
              {detailLoading ? (
                <div className="space-y-4">
                  <Skeleton className="h-6 w-3/4" />
                  <Skeleton className="h-4 w-1/2" />
                  <Skeleton className="h-20 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : selectedInstance ? (
                <>
                  {/* Status card */}
                  <Card className="p-4">
                    <div className="flex items-center justify-between mb-3">
                      <Badge
                        variant={STATUS_BADGE_VARIANT[selectedInstance.status] || 'neutral'}
                        size="md"
                      >
                        {STATUS_LABELS[selectedInstance.status] || capitalize(selectedInstance.status)}
                      </Badge>
                      <span className="text-xs text-[var(--color-text-muted)]">
                        #{selectedInstance.id}
                      </span>
                    </div>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-[var(--color-text-tertiary)]">Type</span>
                        <span className="font-medium text-[var(--color-text-primary)]">
                          {getEntityLabel(selectedInstance.entity_type)}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[var(--color-text-tertiary)]">Entity</span>
                        <span className="font-medium text-[var(--color-text-primary)]">
                          #{selectedInstance.entity_id}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[var(--color-text-tertiary)]">Workflow</span>
                        <span className="font-medium text-[var(--color-text-primary)]">
                          {selectedInstance.workflow?.name || `#${selectedInstance.workflow_id}`}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[var(--color-text-tertiary)]">Created</span>
                        <span className="font-medium text-[var(--color-text-primary)]">
                          {formatDateTime(selectedInstance.created_at)}
                        </span>
                      </div>
                      {selectedInstance.workflow && (
                        <div className="flex justify-between">
                          <span className="text-[var(--color-text-tertiary)]">Current Step</span>
                          <span className="font-medium text-[var(--color-text-primary)]">
                            {/* Look up current step name from workflow steps */}
                            {selectedInstance.workflow.steps?.find(
                              (s) => s.id === selectedInstance.current_step_id
                            )?.label || `Step #${selectedInstance.current_step_id}`}
                          </span>
                        </div>
                      )}
                      {/* Entity link */}
                      <div className="pt-2">
                        <a
                          href={getEntityUrl(selectedInstance.entity_type, selectedInstance.entity_id)}
                          className="text-[var(--color-brand-accent)] text-xs font-medium hover:underline"
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          View related record →
                        </a>
                      </div>
                    </div>
                  </Card>

                  {/* Action area (only for active instances) */}
                  {selectedInstance.status === 'active' && (
                    <Card className="p-4 space-y-3">
                      <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Take Action</h3>

                      {actionError && (
                        <Alert variant="error" onClose={() => setActionError(null)}>
                          {actionError}
                        </Alert>
                      )}

                      <div className="space-y-1.5">
                        <label className="text-sm font-medium text-[var(--color-text-primary)]">
                          Comment (optional)
                        </label>
                        <textarea
                          className="w-full min-h-[80px] px-3 py-2 text-sm rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-accent)] focus:border-transparent transition-shadow resize-none"
                          placeholder="Add a note about your decision..."
                          value={actionComment}
                          onChange={(e) => setActionComment(e.target.value)}
                          rows={3}
                        />
                      </div>

                      <div className="flex flex-wrap gap-2 pt-1">
                        {availableTransitions.some((t) => t.label?.toLowerCase() === 'approve') && (
                          <Button
                            variant="success"
                            size="sm"
                            onClick={() => setConfirmAction('approve')}
                            loading={actionLoading && confirmAction === 'approve'}
                          >
                            <svg className="h-4 w-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                            Approve
                          </Button>
                        )}

                        {availableTransitions.some((t) => t.label?.toLowerCase() === 'reject') && (
                          <Button
                            variant="danger"
                            size="sm"
                            onClick={() => setConfirmAction('reject')}
                            loading={actionLoading && confirmAction === 'reject'}
                          >
                            <svg className="h-4 w-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                            Reject
                          </Button>
                        )}

                        {availableTransitions.some((t) => t.label?.toLowerCase().includes('return')) && (
                          <Button
                            variant="warning"
                            size="sm"
                            onClick={() => setConfirmAction('return')}
                            loading={actionLoading && confirmAction === 'return'}
                          >
                            <svg className="h-4 w-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                            </svg>
                            Return
                          </Button>
                        )}
                      </div>
                    </Card>
                  )}

                  {/* Completed/Cancelled badge for non-active */}
                  {selectedInstance.status !== 'active' && (
                    <Card className="p-4">
                      <div className="flex items-center gap-3">
                        <div className={cn(
                          'h-10 w-10 rounded-xl flex items-center justify-center',
                          selectedInstance.status === 'completed' ? 'bg-emerald-50 dark:bg-emerald-900/20' : 'bg-red-50 dark:bg-red-900/20'
                        )}>
                          {selectedInstance.status === 'completed' ? (
                            <svg className="h-5 w-5 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                          ) : (
                            <svg className="h-5 w-5 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                          )}
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-[var(--color-text-primary)]">
                            {selectedInstance.status === 'completed' ? 'Approved' : 'Rejected'}
                          </p>
                          <p className="text-xs text-[var(--color-text-tertiary)]">
                            This workflow has been resolved. View the history below for details.
                          </p>
                        </div>
                      </div>
                    </Card>
                  )}

                  {/* History timeline */}
                  <div>
                    <button
                      onClick={() => setShowHistory(!showHistory)}
                      className="flex items-center gap-2 text-sm font-semibold text-[var(--color-text-primary)] mb-3 hover:text-[var(--color-brand-accent)] transition-colors"
                    >
                      <svg className={cn(
                        'h-4 w-4 transition-transform duration-200',
                        showHistory && 'rotate-90'
                      )} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                      History ({selectedInstance.history?.length || 0})
                    </button>

                    {showHistory && (
                      <div className="relative pl-6 space-y-0">
                        {/* Vertical timeline line */}
                        <div className="absolute left-[11px] top-1 bottom-1 w-0.5 bg-[var(--color-border)]" />

                        {(selectedInstance.history || []).map((entry, idx) => {
                          const isFirst = idx === 0
                          const isLast = idx === (selectedInstance.history?.length || 0) - 1
                          return (
                            <div key={entry.id} className="relative pb-4 last:pb-0">
                              {/* Timeline dot */}
                              <div className={cn(
                                'absolute left-[-17px] top-1.5 h-[10px] w-[10px] rounded-full border-2',
                                entry.action === 'submit' ? 'border-[var(--color-brand-accent)] bg-[var(--color-brand-accent-subtle)]' :
                                entry.action === 'approve' ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20' :
                                entry.action === 'reject' ? 'border-red-500 bg-red-50 dark:bg-red-900/20' :
                                'border-[var(--color-text-muted)] bg-[var(--color-surface)]'
                              )} />

                              {/* Content */}
                              <div className="bg-[var(--color-surface-hover)] rounded-lg p-3">
                                <div className="flex items-center justify-between gap-2">
                                  <Badge
                                    variant={ACTION_VARIANTS[entry.action] || 'neutral'}
                                    size="sm"
                                  >
                                    {capitalize(entry.action)}
                                  </Badge>
                                  <span className="text-[11px] text-[var(--color-text-muted)] whitespace-nowrap">
                                    {formatDateTime(entry.created_at)}
                                  </span>
                                </div>
                                <p className="text-xs text-[var(--color-text-tertiary)] mt-1.5">
                                  by {getActorLabel(entry)}
                                </p>
                                {entry.comment && (
                                  <p className="text-sm text-[var(--color-text-secondary)] mt-1.5 italic bg-[var(--color-surface)] rounded-md px-2.5 py-1.5 border border-[var(--color-border-light)]">
                                    "{entry.comment}"
                                  </p>
                                )}
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>

                  {/* Available transitions info */}
                  {availableTransitions.length > 0 && selectedInstance.status === 'active' && (
                    <div className="text-xs text-[var(--color-text-muted)] pt-2 border-t border-[var(--color-border-light)]">
                      <p>Available actions: {availableTransitions.map((t) => t.label).filter(Boolean).join(', ')}</p>
                    </div>
                  )}
                </>
              ) : (
                <EmptyState
                  title="Could not load detail"
                  description="The instance detail could not be retrieved."
                />
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Confirmation dialog ── */}
      <ConfirmDialog
        open={!!confirmAction}
        onClose={() => setConfirmAction(null)}
        onConfirm={() => handleAction(confirmAction!)}
        title={
          confirmAction === 'approve' ? 'Confirm Approval' :
          confirmAction === 'reject' ? 'Confirm Rejection' :
          'Confirm Return'
        }
        message={
          confirmAction === 'approve'
            ? 'Are you sure you want to approve this request? This will advance the workflow to the next step.'
            : confirmAction === 'reject'
            ? 'Are you sure you want to reject this request? This action cannot be undone.'
            : 'Are you sure you want to return this request for revision? The submitter will need to revise and resubmit.'
        }
        confirmLabel={
          confirmAction === 'approve' ? 'Approve' :
          confirmAction === 'reject' ? 'Reject' : 'Return'
        }
        variant={
          confirmAction === 'approve' ? 'primary' :
          confirmAction === 'reject' ? 'danger' : 'warning'
        }
        loading={actionLoading}
      />
    </div>
  )
}
