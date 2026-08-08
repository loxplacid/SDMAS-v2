import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import {
  casesApi,
  type AssignableUser,
  type CaseDetail,
  type CasePriority,
  type CaseStatus,
} from '../../api/cases/cases-api'
import { Badge, Button, Modal, Skeleton } from '../../components/ui'
import { useToast } from '../../components/ui/toast'
import { cn, formatDateTime } from '../../lib/utils'

// ── Presentation helpers ─────────────────────────────────────────────

const PRIORITY_BADGE: Record<string, 'danger' | 'warning' | 'info' | 'neutral'> = {
  critical: 'danger',
  high: 'danger',
  medium: 'warning',
  low: 'info',
}

const STATUS_LABELS: Record<string, string> = {
  open: 'Open',
  acknowledged: 'Acknowledged',
  in_progress: 'In Progress',
  waiting: 'Waiting',
  resolved: 'Resolved',
  closed: 'Closed',
}

const STATUS_BADGE: Record<string, 'warning' | 'info' | 'success' | 'neutral'> = {
  open: 'warning',
  acknowledged: 'info',
  in_progress: 'info',
  waiting: 'neutral',
  resolved: 'success',
  closed: 'neutral',
}

const TYPE_LABELS: Record<string, string> = {
  attendance: 'Attendance',
  finance: 'Finance',
  academic: 'Academic',
  documents: 'Documents',
  data_quality: 'Data Quality',
  admissions: 'Admissions',
  operational: 'Operational',
  administrative: 'Administrative',
}

const EVENT_LABELS: Record<string, string> = {
  CASE_CREATED: 'Created',
  ASSIGNED: 'Assigned',
  REASSIGNED: 'Reassigned',
  STATUS_CHANGED: 'Status changed',
  PRIORITY_CHANGED: 'Priority changed',
  COMMENT_ADDED: 'Comment',
  EVIDENCE_ADDED: 'Evidence added',
  DUE_DATE_CHANGED: 'Deadline changed',
  RESOLVED: 'Resolved',
  REOPENED: 'Reopened',
  CLOSED: 'Closed',
  ESCALATED: 'Escalated',
}

const EVENT_DOT: Record<string, string> = {
  CASE_CREATED: 'bg-[var(--color-brand-accent)]',
  RESOLVED: 'bg-[var(--color-success)]',
  CLOSED: 'bg-[var(--color-success)]',
  ESCALATED: 'bg-[var(--color-danger)]',
  REOPENED: 'bg-[var(--color-warning)]',
}

const EVIDENCE_KIND_LABELS: Record<string, string> = {
  attendance_report: 'Attendance report',
  fee_receipt: 'Fee receipt',
  student_document: 'Student document',
  exported_report: 'Exported report',
  administrative_note: 'Administrative note',
}

const SLA_STYLE: Record<string, { badge: 'danger' | 'warning' | 'success' | 'neutral'; label: string }> = {
  OVERDUE: { badge: 'danger', label: 'Overdue' },
  DUE_SOON: { badge: 'warning', label: 'Due soon' },
  ON_TRACK: { badge: 'neutral', label: 'On track' },
  RESOLVED: { badge: 'success', label: 'Resolved' },
}

function resolveDisabled(
  action: { kind: string } | null,
  actionValue: string,
  actionReason: string
): boolean {
  if (!action) return true
  // Resolve requires a reason (audit trail); evidence needs a kind; all
  // other actions need a selection value.
  if (action.kind === 'resolve') return actionReason.trim().length === 0
  if (action.kind === 'evidence') return actionValue.length === 0
  return actionValue.length === 0
}

function SkeletonPage() {
  return (
    <div className="space-y-6 animate-fade-in" aria-busy="true" aria-label="Loading case">
      <div className="space-y-3">
        <Skeleton className="h-8 w-72" />
        <Skeleton className="h-4 w-96" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <Skeleton className="h-48 rounded-2xl" />
          <Skeleton className="h-64 rounded-2xl" />
        </div>
        <Skeleton className="h-96 rounded-2xl" />
      </div>
    </div>
  )
}

// ── Main page ────────────────────────────────────────────────────────

export function CaseDetailPage() {
  const { id } = useParams()
  const caseId = Number(id)
  const { user } = useAuth()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const role = (user?.role as string) || 'staff'
  const canLead = ['admin', 'principal'].includes(role)

  const [detail, setDetail] = useState<CaseDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [assignable, setAssignable] = useState<AssignableUser[]>([])
  const [comment, setComment] = useState('')
  const [posting, setPosting] = useState(false)

  const [action, setAction] = useState<
    | { kind: 'assign' }
    | { kind: 'transition' }
    | { kind: 'priority' }
    | { kind: 'evidence' }
    | { kind: 'resolve' }
    | null
  >(null)
  const [actionValue, setActionValue] = useState('')
  const [actionReason, setActionReason] = useState('')
  const [busy, setBusy] = useState(false)
  const fetchIdRef = useRef(0)

  // Background refresh: after a mutation the server response is already
  // applied optimistically via setDetail, so re-fetching must not flash the
  // skeleton. Only the initial load uses the loading state.
  const refresh = useCallback(async () => {
    if (!Number.isInteger(caseId) || caseId <= 0) return
    const fetchId = ++fetchIdRef.current
    try {
      const data = await casesApi.get(caseId)
      if (fetchId === fetchIdRef.current) setDetail(data)
    } catch {
      // Keep the optimistic state; the next explicit load will surface errors.
    }
  }, [caseId])

  const load = useCallback(async () => {
    if (!Number.isInteger(caseId) || caseId <= 0) {
      setError('Invalid case id')
      setLoading(false)
      return
    }
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    try {
      const data = await casesApi.get(caseId)
      if (fetchId === fetchIdRef.current) setDetail(data)
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) {
        setError(err?.detail || 'Unable to load this case')
      }
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    casesApi.assignable().then(setAssignable).catch(() => {})
  }, [])

  const runAction = async () => {
    if (!detail || !action) return
    setBusy(true)
    try {
      const c = detail.case
      if (action.kind === 'assign') {
        const updated = await casesApi.assign(c.id, Number(actionValue), actionReason || null, c.version)
        setDetail((d) => (d ? { ...d, case: updated } : d))
        showToast(`Assigned ${updated.case_number}`, 'success')
      } else if (action.kind === 'transition') {
        const updated = await casesApi.transition(c.id, actionValue as CaseStatus, actionReason || null, c.version)
        setDetail((d) => (d ? { ...d, case: updated } : d))
        showToast(`Status changed to ${updated.status.replace('_', ' ')}`, 'success')
      } else if (action.kind === 'priority') {
        const updated = await casesApi.changePriority(c.id, actionValue as CasePriority, actionReason || null, c.version)
        setDetail((d) => (d ? { ...d, case: updated } : d))
        showToast('Priority updated (audited)', 'success')
      } else if (action.kind === 'evidence') {
        await casesApi.addEvidence(c.id, {
          kind: actionValue,
          title: actionReason || 'Supporting evidence',
        })
        showToast('Evidence attached (audited)', 'success')
      } else if (action.kind === 'resolve') {
        const updated = await casesApi.transition(c.id, 'resolved', actionReason || 'Resolved by staff', c.version)
        setDetail((d) => (d ? { ...d, case: updated } : d))
        showToast(`Case ${updated.case_number} resolved`, 'success')
      }
      setAction(null)
      setActionValue('')
      setActionReason('')
      await refresh()
    } catch (err: any) {
      showToast(err?.detail || 'Action failed — the case may have changed. Reloading.', 'error')
      await refresh()
    } finally {
      setBusy(false)
    }
  }

  const postComment = async () => {
    if (!detail || !comment.trim()) return
    setPosting(true)
    try {
      await casesApi.addComment(detail.case.id, comment.trim())
      setComment('')
      showToast('Comment added (audited)', 'success')
      await refresh()
    } catch (err: any) {
      showToast(err?.detail || 'Failed to add comment', 'error')
    } finally {
      setPosting(false)
    }
  }

  if (loading) return <SkeletonPage />
  if (error || !detail) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center animate-fade-in">
        <div className="h-14 w-14 rounded-2xl bg-[var(--color-danger-light)] flex items-center justify-center mb-5">
          <svg className="h-7 w-7 text-[var(--color-danger)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
        </div>
        <h3 className="text-sm font-semibold text-[var(--color-danger-dark)]">{error}</h3>
        <button
          onClick={() => navigate('/work')}
          className="mt-5 inline-flex items-center rounded-[10px] bg-[var(--color-brand-accent)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--color-brand-accent-hover)] motion-safe:transition-colors"
        >
          Back to work queue
        </button>
      </div>
    )
  }

  const c = detail.case
  const sla = SLA_STYLE[c.sla_state] || SLA_STYLE.ON_TRACK
  const open = c.status !== 'resolved' && c.status !== 'closed'

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-mono font-bold text-[var(--color-brand-accent)]">{c.case_number}</span>
            <Badge variant={PRIORITY_BADGE[c.priority]} size="sm">{c.priority}</Badge>
            <Badge variant={STATUS_BADGE[c.status]} size="sm">{STATUS_LABELS[c.status]}</Badge>
            <Badge variant={sla.badge} size="sm">{sla.label}</Badge>
            <Badge variant="neutral" size="sm">{TYPE_LABELS[c.case_type] || c.case_type}</Badge>
            {c.escalated_at && <Badge variant="danger" size="sm">Escalated</Badge>}
          </div>
          <h1 className="text-2xl font-bold text-[var(--color-text-primary)] mt-2 tracking-tight">{c.title}</h1>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-1.5">
            {c.assignee_name ? `Assigned to ${c.assignee_name}` : 'Unassigned'}
            {c.due_at ? ` · Due ${formatDateTime(c.due_at)}` : ' · No deadline'}
            {c.resolved_reason && ` · Resolved: ${c.resolved_reason}`}
          </p>
          {c.description && <p className="text-sm text-[var(--color-text-secondary)] mt-3 max-w-2xl">{c.description}</p>}
        </div>

        <div className="flex flex-wrap items-center gap-2 flex-shrink-0">
          <Button variant="outline" size="sm" onClick={() => navigate('/work')}>Work Queue</Button>
          {canLead && (
            <>
              <Button variant="outline" size="sm" onClick={() => setAction({ kind: 'assign' })}>Assign</Button>
              <Button variant="outline" size="sm" onClick={() => setAction({ kind: 'priority' })}>Priority</Button>
              {open && (
                <Button variant="outline" size="sm" onClick={() => setAction({ kind: 'transition' })}>Status</Button>
              )}
              <Button variant="outline" size="sm" onClick={() => setAction({ kind: 'evidence' })}>Evidence</Button>
              {open && (
                <Button size="sm" onClick={() => setAction({ kind: 'resolve' })}>Resolve</Button>
              )}
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: source + timeline */}
        <div className="lg:col-span-2 space-y-6">
          {/* Source reference */}
          <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
            <h2 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Source</h2>
            {c.source_type === 'manual' ? (
              <p className="text-sm text-[var(--color-text-tertiary)]">Created manually by a user.</p>
            ) : (
              <div className="flex items-center justify-between gap-4 flex-wrap">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[var(--color-text-primary)]">
                    {c.source_type === 'risk_finding' ? 'Risk finding' : 'Data-quality finding'} #{c.source_id}
                  </p>
                  <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">
                    This case references the original P7 finding — its data is never duplicated here.
                  </p>
                </div>
                <button
                  onClick={() => navigate(c.source_type === 'risk_finding' ? '/risk' : '/data-quality')}
                  className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] px-3 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/40 hover:text-[var(--color-brand-accent)] motion-safe:transition-colors"
                >
                  View underlying records
                </button>
              </div>
            )}
            {c.student_id && (
              <button
                onClick={() => navigate(`/students/${c.student_id}`)}
                className="mt-3 text-xs font-medium text-[var(--color-brand-accent)] hover:underline"
              >
                Related student #{c.student_id} →
              </button>
            )}
          </section>

          {/* Activity timeline */}
          <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
            <h2 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Activity</h2>
            {detail.events.length === 0 ? (
              <p className="text-sm text-[var(--color-text-tertiary)] py-6 text-center">No activity recorded yet.</p>
            ) : (
              <ol className="relative space-y-5 before:absolute before:left-[5px] before:top-1.5 before:bottom-1.5 before:w-px before:bg-[var(--color-border)]">
                {[...detail.events].reverse().map((e) => (
                  <li key={e.id} className="relative pl-7">
                    <span
                      className={cn(
                        'absolute left-0 top-1.5 h-[11px] w-[11px] rounded-full border-2 border-[var(--color-bg)]',
                        EVENT_DOT[e.event_type] || 'bg-[var(--color-text-muted)]'
                      )}
                      aria-hidden="true"
                    />
                    <div className="flex items-baseline justify-between gap-3">
                      <p className="text-sm font-medium text-[var(--color-text-primary)]">
                        {EVENT_LABELS[e.event_type] || e.event_type}
                      </p>
                      <span className="text-[11px] text-[var(--color-text-muted)] flex-shrink-0">
                        {formatDateTime(e.created_at)}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">
                      {e.message}
                      {e.actor_name ? ` — ${e.actor_name}` : ''}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </section>

          {/* Evidence */}
          <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
            <h2 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Evidence</h2>
            {detail.evidence.length === 0 ? (
              <p className="text-sm text-[var(--color-text-tertiary)] py-4 text-center">No evidence attached.</p>
            ) : (
              <ul className="space-y-2">
                {detail.evidence.map((ev) => (
                  <li key={ev.id} className="flex items-start gap-3 rounded-xl border border-[var(--color-border)] p-3">
                    <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-[var(--color-surface-hover)] flex-shrink-0">
                      <svg className="h-4 w-4 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-[var(--color-text-primary)]">{ev.title}</p>
                      <p className="text-xs text-[var(--color-text-tertiary)]">
                        {EVIDENCE_KIND_LABELS[ev.kind] || ev.kind}
                        {ev.reference_id ? ` · ref ${ev.reference_type}#${ev.reference_id}` : ''}
                        {ev.summary ? ` · ${ev.summary}` : ''}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        {/* Right: comments + actions */}
        <div className="space-y-6">
          {/* Comments */}
          <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
            <h2 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Comments</h2>
            <div className="space-y-3 mb-4 max-h-72 overflow-y-auto">
              {detail.comments.length === 0 ? (
                <p className="text-sm text-[var(--color-text-tertiary)] py-4 text-center">No comments yet.</p>
              ) : (
                detail.comments.map((cm) => (
                  <div key={cm.id} className="rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] p-3">
                    <div className="flex items-baseline justify-between gap-2">
                      <p className="text-xs font-semibold text-[var(--color-text-primary)]">{cm.author_name || 'Unknown'}</p>
                      <span className="text-[10px] text-[var(--color-text-muted)]">{formatDateTime(cm.created_at)}</span>
                    </div>
                    <p className="text-xs text-[var(--color-text-secondary)] mt-1 leading-relaxed whitespace-pre-wrap">{cm.body}</p>
                  </div>
                ))
              )}
            </div>
            <div className="flex items-end gap-2">
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Add a comment (audited, immutable)…"
                rows={2}
                className="flex-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-brand-accent)] focus:outline-none resize-none"
              />
              <Button size="sm" onClick={postComment} disabled={posting || !comment.trim()}>
                {posting ? '…' : 'Post'}
              </Button>
            </div>
          </section>

          {/* Case facts */}
          <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
            <h2 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Details</h2>
            <dl className="space-y-2.5 text-sm">
              {[
                { k: 'Created', v: formatDateTime(c.created_at) },
                { k: 'Updated', v: formatDateTime(c.updated_at) },
                { k: 'Original priority', v: c.original_priority },
                { k: 'Source', v: c.source_type.replace('_', ' ') },
                { k: 'Assigned at', v: c.assigned_at ? formatDateTime(c.assigned_at) : '—' },
                { k: 'Resolved at', v: c.resolved_at ? formatDateTime(c.resolved_at) : '—' },
                { k: 'Closed at', v: c.closed_at ? formatDateTime(c.closed_at) : '—' },
              ].map((row) => (
                <div key={row.k} className="flex items-center justify-between gap-3">
                  <dt className="text-xs text-[var(--color-text-tertiary)]">{row.k}</dt>
                  <dd className="text-xs font-medium text-[var(--color-text-primary)]">{row.v}</dd>
                </div>
              ))}
            </dl>
          </section>
        </div>
      </div>

      {/* Action modals */}
      <Modal
        open={action != null}
        onClose={() => setAction(null)}
        title={
          action?.kind === 'assign' ? 'Assign case'
            : action?.kind === 'priority' ? 'Change priority'
            : action?.kind === 'transition' ? 'Change status'
            : action?.kind === 'evidence' ? 'Attach evidence'
            : action?.kind === 'resolve' ? 'Resolve case'
            : ''
        }
        size="sm"
        footer={
          <>
            <Button variant="outline" size="sm" onClick={() => setAction(null)}>Cancel</Button>
            <Button
              size="sm"
              onClick={runAction}
              disabled={busy || resolveDisabled(action, actionValue, actionReason)}
            >
              {busy ? 'Saving…' : 'Apply'}
            </Button>
          </>
        }
      >
        {action?.kind === 'assign' && (
          <select
            value={actionValue}
            onChange={(e) => setActionValue(e.target.value)}
            className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
            aria-label="Assign to"
          >
            <option value="">Select assignee…</option>
            {assignable.map((u) => (
              <option key={u.id} value={u.id}>{u.name} · {u.role}</option>
            ))}
          </select>
        )}
        {action?.kind === 'priority' && (
          <select
            value={actionValue}
            onChange={(e) => setActionValue(e.target.value)}
            className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
            aria-label="New priority"
          >
            <option value="">Select priority…</option>
            {(['critical', 'high', 'medium', 'low'] as const).map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        )}
        {action?.kind === 'transition' && (
          <select
            value={actionValue}
            onChange={(e) => setActionValue(e.target.value)}
            className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
            aria-label="New status"
          >
            <option value="">Select status…</option>
            {Object.entries(STATUS_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        )}
        {action?.kind === 'evidence' && (
          <select
            value={actionValue}
            onChange={(e) => setActionValue(e.target.value)}
            className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
            aria-label="Evidence kind"
          >
            <option value="">Select kind…</option>
            {Object.entries(EVIDENCE_KIND_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        )}
        {action?.kind === 'resolve' && (
          <p className="text-xs text-[var(--color-text-tertiary)]">
            Resolving requires a reason — it is recorded in the immutable audit trail.
          </p>
        )}
        <textarea
          value={actionReason}
          onChange={(e) => setActionReason(e.target.value)}
          placeholder={action?.kind === 'evidence' ? 'Evidence title (audited)' : 'Reason (audited) — optional for status, required for resolve'}
          rows={2}
          className="mt-3 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-brand-accent)] focus:outline-none resize-none"
        />
      </Modal>
    </div>
  )
}

export default CaseDetailPage
