import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { casesApi, type CaseItem, type CasePriority, type CaseType } from '../../api/cases/cases-api'
import type { Student360Response } from '../../api/student-360/student-360-api'
import { Badge, Button, Input, Select } from '../../components/ui'
import { useToast } from '../../components/ui/toast'
import { useAuth } from '../../api/auth/auth-context'
import { usePermission } from '../../hooks/use-permission'
import { FEES_VIEW } from '../../types/permissions'
import { cn } from '../../lib/utils'

/**
 * P10 — Unified Student Object operational summary.
 *
 * A persistent strip rendered above the Student 360 tabs that answers
 * "what is the state of this student" without leaving the record:
 *
 *   status / class-section / year
 *   attendance signal · financial signal · open findings · active cases
 *   state-driven contextual actions (only shown when the state is real)
 *
 * Every value is derived from the actual 360 response or the cases API —
 * nothing is invented.  The attendance "at-risk" cut-off mirrors the
 * product rule already used by the 360 page (75%); finance findings are
 * hidden from roles without FEES_VIEW; cases are only fetched by roles
 * the backend allows on /api/cases (admin/principal/staff) and degrade
 * silently for everyone else.
 */

/**
 * Canonical student-status maps — shared by Student 360 and the operational
 * summary so the two never drift. Exported from here because the summary is
 * the identity-aware header of the unified object.
 */
export const statusBadgeVariant: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  prospective: 'info',
  admitted: 'info',
  enrolled: 'info',
  active: 'success',
  transferred: 'warning',
  withdrawn: 'danger',
  graduated: 'info',
  alumni: 'info',
  inactive: 'danger',
}

export const statusLabel: Record<string, string> = {
  prospective: 'Prospective',
  admitted: 'Admitted',
  enrolled: 'Enrolled',
  active: 'Active',
  transferred: 'Transferred',
  withdrawn: 'Withdrawn',
  graduated: 'Graduated',
  alumni: 'Alumni',
  inactive: 'Inactive',
}

// Severity/priority -> signal tone (deterministic, matches risk UI colors).
const casePriorityTone: Record<string, 'alert' | 'warn' | 'ok' | 'muted'> = {
  critical: 'alert',
  high: 'alert',
  medium: 'warn',
  low: 'ok',
}

const findingSeverityTone: Record<string, 'alert' | 'warn' | 'ok' | 'muted'> = {
  critical: 'alert',
  high: 'alert',
  medium: 'warn',
  low: 'ok',
}

const SEVERITY_RANK: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 }

const toneDot: Record<string, string> = {
  ok: 'bg-[var(--color-success)]',
  warn: 'bg-[var(--color-warning)]',
  alert: 'bg-[var(--color-danger)]',
  muted: 'bg-[var(--color-text-tertiary)]',
}

const toneText: Record<string, string> = {
  ok: 'text-[var(--color-success-dark)]',
  warn: 'text-[var(--color-warning-dark)]',
  alert: 'text-[var(--color-danger-dark)]',
  muted: 'text-[var(--color-text-tertiary)]',
}

//: Roles allowed to work the cases queue (backend require_role contract).
const CASE_ROLES = new Set(['admin', 'principal', 'staff'])

function SignalCell({
  label,
  value,
  tone,
  hint,
  onClick,
  ariaLabel,
}: {
  label: string
  value: string
  tone: 'ok' | 'warn' | 'alert' | 'muted'
  hint?: string
  onClick?: () => void
  ariaLabel?: string
}) {
  const cellClasses = cn(
    'flex flex-col items-start gap-1 px-5 py-3.5 text-left min-w-0',
    'border-b border-[var(--color-border)] last:border-b-0',
    'md:border-b-0 md:border-r md:last:border-r-0'
  )
  const inner = (
    <>
      <span className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-[var(--color-text-tertiary)]">
        <span className={cn('inline-block h-1.5 w-1.5 rounded-full', toneDot[tone])} aria-hidden="true" />
        {label}
      </span>
      <span className={cn('text-lg font-semibold leading-tight tabular-nums', toneText[tone])}>{value}</span>
      {hint && <span className="text-[11px] text-[var(--color-text-tertiary)] truncate max-w-full">{hint}</span>}
    </>
  )
  if (!onClick) {
    // Non-actionable signal: a plain cell, not a disabled button (a11y).
    return (
      <div data-signal="" className={cn(cellClasses, 'cursor-default')}>
        {inner}
      </div>
    )
  }
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={ariaLabel}
      data-signal=""
      className={cn(cellClasses, 'hover:bg-[var(--color-surface-hover)] motion-safe:transition-colors')}
    >
      {inner}
    </button>
  )
}

function CaseListPreview({ cases }: { cases: CaseItem[] }) {
  return (
    <ul className="mt-2.5 space-y-1.5">
      {cases.slice(0, 3).map((c) => (
        <li key={c.id} className="flex items-center gap-2 text-xs">
          <span className="font-mono font-medium text-[var(--color-text-primary)]">{c.case_number}</span>
          <Badge variant={c.priority === 'critical' || c.priority === 'high' ? 'danger' : c.priority === 'medium' ? 'warning' : 'info'} size="sm">
            {c.priority}
          </Badge>
          <span className="truncate text-[var(--color-text-muted)]">{c.title}</span>
          <span className={cn(
            'ml-auto shrink-0 font-medium',
            c.sla_state === 'OVERDUE' ? 'text-[var(--color-danger)]' : c.sla_state === 'DUE_SOON' ? 'text-[var(--color-warning-dark)]' : 'text-[var(--color-text-tertiary)]'
          )}>
            {c.sla_state === 'ON_TRACK' ? 'on track' : c.sla_state.toLowerCase().replace('_', ' ')}
          </span>
        </li>
      ))}
    </ul>
  )
}

export interface OperationalSummaryProps {
  data: Student360Response
  /** Jump to a 360 tab (attendance | finance | risk). */
  onOpenTab: (tab: string) => void
}

export function OperationalSummary({ data, onOpenTab }: OperationalSummaryProps) {
  const navigate = useNavigate()
  const { can } = usePermission()
  const { user } = useAuth()
  const { showToast } = useToast()

  const identity = data.identity
  const ce = data.current_enrollment
  const canViewFees = can(FEES_VIEW)
  const canWorkCases = user ? CASE_ROLES.has(user.role) : false

  // Active cases — loaded from the real work queue, scoped to this student.
  const [cases, setCases] = useState<CaseItem[] | null>(null)
  const [casesError, setCasesError] = useState(false)
  useEffect(() => {
    if (!canWorkCases) {
      setCases([])
      setCasesError(false)
      return
    }
    let active = true
    setCases(null)
    setCasesError(false)
    casesApi
      .list({ student_id: identity.id, view: 'open', sort: 'priority', size: 3 })
      .then((res) => {
        if (active) setCases(res?.items ?? [])
      })
      .catch(() => {
        if (active) {
          setCases([])
          setCasesError(true)
        }
      })
    return () => {
      active = false
    }
  }, [identity.id, canWorkCases])

  // ── Deterministic signals ──────────────────────────────────────────
  // The 360 aggregate always carries these modules, but degrade honestly
  // (P10 spec: "missing modules") instead of crashing if one is absent.
  const attendance = data.attendance
  const attTotal = attendance?.total ?? 0
  const attPct = attendance?.percentage ?? 0
  const attendanceAtRisk = attTotal > 0 && attPct < 75 // product rule already used by the 360 page

  const financial = data.financial
  const outstanding = financial?.total_outstanding ?? 0
  const unpaidDueCount = (financial?.unpaid_count ?? 0) + (financial?.partially_paid_count ?? 0)

  const findings = data.risk_findings ?? []
  const topFindingSeverity = [...findings]
    .sort((a, b) => (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9))[0]?.severity

  const openCases = cases ?? []
  const topCase = openCases[0]

  // ── Create-case flow ────────────────────────────────────────────────
  const [creating, setCreating] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [title, setTitle] = useState('')
  const [caseType, setCaseType] = useState<CaseType>('administrative')
  const [priority, setPriority] = useState<CasePriority>('medium')

  const handleCreateCase = async () => {
    if (!title.trim()) return
    setCreating(true)
    try {
      const created = await casesApi.create({
        title: title.trim(),
        case_type: caseType,
        priority,
        student_id: identity.id,
        description: `Created from Student 360 — ${identity.first_name} ${identity.last_name} (${identity.student_number})`,
      })
      showToast(`Case ${created.case_number} created`, 'success')
      navigate(`/cases/${created.id}`)
    } catch (err: any) {
      showToast(err?.detail || 'Failed to create case', 'error')
    } finally {
      setCreating(false)
    }
  }

  return (
    <section aria-label="Operational summary" className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
      {/* Identity strip */}
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-5 py-3">
        <div className="flex flex-wrap items-center gap-2.5 min-w-0">
          <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)]">Operational Status</span>
          <Badge variant={statusBadgeVariant[identity.status]}>{statusLabel[identity.status] ?? identity.status}</Badge>
          {ce && (
            <span className="text-sm text-[var(--color-text-muted)]">
              {[ce.class_name, ce.section_name].filter(Boolean).join(' - ')}
              <span className="text-[var(--color-text-tertiary)]"> · {ce.academic_year_name}</span>
            </span>
          )}
        </div>
        <span className="text-xs text-[var(--color-text-tertiary)] shrink-0">Student #{identity.student_number}</span>
      </div>

      {/* Signals */}
      <div className="grid grid-cols-2 md:grid-cols-4 border-t border-[var(--color-border)]">
        <SignalCell
          label="Attendance"
          value={attTotal === 0 ? '—' : `${attPct}%`}
          tone={attTotal === 0 ? 'muted' : attendanceAtRisk ? 'alert' : 'ok'}
          hint={attTotal === 0 ? undefined : attendanceAtRisk ? 'Below the 75% threshold' : undefined}
          onClick={attTotal > 0 ? () => onOpenTab('attendance') : undefined}
          ariaLabel="Open attendance tab"
        />
        {canViewFees && !financial ? (
          <SignalCell label="Finance" value="—" tone="muted" hint="No finance data" />
        ) : canViewFees ? (
          <SignalCell
            label="Finance"
            value={outstanding === 0 ? 'Clear' : `$${outstanding.toLocaleString()}`}
            tone={outstanding === 0 ? 'ok' : 'alert'}
            hint={unpaidDueCount > 0 ? `${unpaidDueCount} unpaid due${unpaidDueCount === 1 ? '' : 's'}` : undefined}
            onClick={outstanding > 0 ? () => onOpenTab('finance') : undefined}
            ariaLabel="Open finance tab"
          />
        ) : (
          <SignalCell label="Finance" value="—" tone="muted" hint="No finance access" />
        )}
        <SignalCell
          label="Open findings"
          value={`${findings.length}`}
          tone={findings.length === 0 ? 'ok' : findingSeverityTone[topFindingSeverity] ?? 'warn'}
          hint={findings.length > 0 ? 'From the risk engine' : undefined}
          onClick={findings.length > 0 ? () => onOpenTab('risk') : undefined}
          ariaLabel="Open risk tab"
        />
        {canWorkCases ? (
          <SignalCell
            label="Active cases"
            value={cases === null ? '…' : `${openCases.length}`}
            tone={cases === null ? 'muted' : casesError ? 'muted' : openCases.length === 0 ? 'ok' : casePriorityTone[topCase?.priority ?? 'medium'] ?? 'ok'}
            hint={casesError ? 'Unavailable' : openCases.length > 0 ? `Top: ${topCase?.case_number}` : undefined}
            onClick={openCases.length > 0 ? () => navigate(`/cases/${topCase!.id}`) : undefined}
            ariaLabel="Open the highest priority case"
          />
        ) : (
          <SignalCell label="Active cases" value="—" tone="muted" hint="Work queue restricted" />
        )}
      </div>

      {/* State-driven contextual actions */}
      <div className="flex flex-wrap items-center gap-2 border-t border-[var(--color-border)] px-5 py-3">
        {attendanceAtRisk && (
          <Button size="sm" variant="outline" onClick={() => onOpenTab('attendance')}>
            Review attendance
          </Button>
        )}
        {canViewFees && outstanding > 0 && (
          <Button size="sm" variant="outline" onClick={() => onOpenTab('finance')}>
            View fee issue
          </Button>
        )}
        {findings.length > 0 && (
          <Button size="sm" variant="outline" onClick={() => onOpenTab('risk')}>
            Review findings ({findings.length})
          </Button>
        )}
        {openCases.length > 0 && (
          <Button size="sm" variant="outline" onClick={() => navigate(`/cases/${topCase!.id}`)}>
            Open case {topCase!.case_number}
          </Button>
        )}
        {canWorkCases && (
          <Button
            size="sm"
            variant={showCreate ? 'secondary' : 'primary'}
            onClick={() => setShowCreate((v) => !v)}
          >
            {showCreate ? 'Cancel' : 'Create case'}
          </Button>
        )}
        <span className="ml-auto text-[11px] text-[var(--color-text-tertiary)]">
          <button
            type="button"
            onClick={() => navigate(`/students/${identity.id}`)}
            className="inline-flex items-center gap-1 hover:text-[var(--color-brand-accent)] motion-safe:transition-colors"
          >
            Full profile
            <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </span>
      </div>

      {/* Case preview */}
      {canWorkCases && openCases.length > 0 && (
        <div className="border-t border-[var(--color-border)] px-5 py-3 bg-[var(--color-surface-hover)]/40">
          <CaseListPreview cases={openCases} />
        </div>
      )}

      {/* Inline create-case form */}
      {showCreate && (
        <div className="border-t border-[var(--color-border)] px-5 py-4 space-y-3 animate-fade-in">
          <div className="grid grid-cols-1 md:grid-cols-[1fr_160px_140px] gap-3">
            <Input
              label="Title"
              id="op-summary-case-title"
              placeholder="e.g. Attendance anomaly — October"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
            <Select
              label="Type"
              id="op-summary-case-type"
              value={caseType}
              onChange={(e) => setCaseType(e.target.value as CaseType)}
              options={[
                { value: 'attendance', label: 'Attendance' },
                { value: 'finance', label: 'Finance' },
                { value: 'academic', label: 'Academic' },
                { value: 'documents', label: 'Documents' },
                { value: 'data_quality', label: 'Data quality' },
                { value: 'operational', label: 'Operational' },
                { value: 'administrative', label: 'Administrative' },
              ]}
            />
            <Select
              label="Priority"
              id="op-summary-case-priority"
              value={priority}
              onChange={(e) => setPriority(e.target.value as CasePriority)}
              options={[
                { value: 'critical', label: 'Critical' },
                { value: 'high', label: 'High' },
                { value: 'medium', label: 'Medium' },
                { value: 'low', label: 'Low' },
              ]}
            />
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={handleCreateCase} loading={creating} disabled={!title.trim()}>
              Create case for {identity.first_name}
            </Button>
            <span className="text-[11px] text-[var(--color-text-tertiary)]">
              An SLA deadline is set from the case type + priority defaults.
            </span>
          </div>
        </div>
      )}
    </section>
  )
}
