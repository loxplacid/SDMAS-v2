import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../api/auth/auth-context'
import type { CasePriority } from '../../api/cases/cases-api'
import {
  riskApi,
  type RiskFinding,
  type RiskFindingPage,
  type RiskOverview,
  type RuleConfig,
  type RecomputeResult,
} from '../../api/risk/risk-api'
import { casesApi } from '../../api/cases/cases-api'
import { Badge, Button, Card, Modal, Skeleton } from '../../components/ui'
import { useToast } from '../../components/ui/toast'
import { cn, formatDateTime } from '../../lib/utils'

// ── Constants ─────────────────────────────────────────────────────────

const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low'] as const

const severityStyles: Record<string, string> = {
  critical: 'border-[var(--color-danger)]/30 bg-[var(--color-danger)]/5',
  high: 'border-[var(--color-danger)]/20 bg-[var(--color-danger)]/[0.04]',
  medium: 'border-[var(--color-warning)]/25 bg-[var(--color-warning)]/5',
  low: 'border-[var(--color-info)]/25 bg-[var(--color-info)]/5',
}

const severityBadge: Record<string, 'danger' | 'warning' | 'info' | 'success'> = {
  critical: 'danger',
  high: 'danger',
  medium: 'warning',
  low: 'info',
}

const severityDot: Record<string, string> = {
  critical: 'bg-[var(--color-danger)]',
  high: 'bg-[var(--color-danger)]',
  medium: 'bg-[var(--color-warning)]',
  low: 'bg-[var(--color-info)]',
}

const severityTint: Record<string, string> = {
  critical: 'text-[var(--color-danger)] bg-[var(--color-danger)]/10',
  high: 'text-[var(--color-danger)] bg-[var(--color-danger)]/10',
  medium: 'text-[var(--color-warning)] bg-[var(--color-warning)]/10',
  low: 'text-[var(--color-info)] bg-[var(--color-info)]/10',
}

const CATEGORY_LABELS: Record<string, string> = {
  attendance: 'Attendance',
  finance: 'Finance',
  academic: 'Academic',
  documents: 'Documents',
  admissions: 'Admissions',
  operational: 'Operational',
}

const STATUS_OPTIONS = [
  { value: 'open', label: 'Open' },
  { value: 'acknowledged', label: 'Acknowledged' },
  { value: 'resolved', label: 'Resolved' },
]

// ── Helpers ───────────────────────────────────────────────────────────

function entityLabel(f: RiskFinding): string {
  if (f.entity_type === 'admission_application') {
    const applicant = (f.evidence?.applicant as string) || `#${f.entity_id}`
    return `Application · ${applicant}`
  }
  const name = f.evidence?.student as string | undefined
  return name ? `Student · ${name}` : `Student #${f.entity_id}`
}

function drillDownFor(f: RiskFinding): string | null {
  if (f.student_id) return `/students/${f.student_id}/360`
  if (f.entity_type === 'admission_application') return `/admissions/${f.entity_id}`
  return null
}

// ── Severity overview cards ───────────────────────────────────────────

function SeverityCard({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 animate-fade-in-up" style={{ animationFillMode: 'both' }}>
      <div className="flex items-center gap-2 mb-1.5">
        <span className={cn('inline-block h-2 w-2 rounded-full', severityDot[tone])} aria-hidden="true" />
        <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)]">{label}</p>
      </div>
      <p className={cn('text-2xl font-bold tabular-nums leading-none', severityTint[tone])}>{value}</p>
    </div>
  )
}

// ── Finding card ──────────────────────────────────────────────────────

function FindingCard({
  finding,
  canResolve,
  canAcknowledge,
  onResolve,
  onAcknowledge,
  onCreateCase,
  index,
}: {
  finding: RiskFinding
  canResolve: boolean
  canAcknowledge: boolean
  onResolve: (f: RiskFinding) => void
  onAcknowledge: (f: RiskFinding) => void
  onCreateCase: (f: RiskFinding) => void
  index: number
}) {
  const navigate = useNavigate()
  const drill = drillDownFor(finding)
  const isActive = finding.status === 'open' || finding.status === 'acknowledged'

  return (
    <div
      className={cn(
        'rounded-xl border p-4 motion-safe:transition-all motion-safe:duration-[var(--motion-fast)] hover:shadow-sm',
        severityStyles[finding.severity],
        'animate-fade-in-up'
      )}
      style={{ animationDelay: `${Math.min(index, 8) * 50}ms`, animationFillMode: 'both' }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0">
          <span className={cn('mt-1.5 inline-block h-2 w-2 rounded-full flex-shrink-0', severityDot[finding.severity])} aria-hidden="true" />
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="text-sm font-semibold text-[var(--color-text-primary)]">{entityLabel(finding)}</p>
              <Badge variant={severityBadge[finding.severity]} size="sm">{finding.severity}</Badge>
              <Badge variant="neutral" size="sm">{CATEGORY_LABELS[finding.category] || finding.category}</Badge>
              {finding.status !== 'open' && (
                <Badge variant={finding.status === 'resolved' ? 'success' : 'warning'} size="sm">{finding.status}</Badge>
              )}
            </div>
            <p className="text-xs text-[var(--color-text-tertiary)] mt-1 leading-relaxed">{finding.reason}</p>
            {finding.status !== 'resolved' && (
              <p className="text-xs text-[var(--color-text-secondary)] mt-1.5">
                <span className="font-medium">Recommended:</span> {finding.recommended_action}
              </p>
            )}
            {finding.status === 'resolved' && finding.resolved_reason && (
              <p className="text-xs text-[var(--color-text-muted)] mt-1.5">
                Resolved: {finding.resolved_reason}
                {finding.resolved_at ? ` · ${formatDateTime(finding.resolved_at)}` : ''}
              </p>
            )}
            <p className="text-[11px] text-[var(--color-text-muted)] mt-1.5">
              Detected {formatDateTime(finding.detected_at)}
              {finding.evidence && finding.evidence.score != null && (
                <span className="ml-2">Score {Number(finding.evidence.score).toFixed(0)}</span>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {isActive && canAcknowledge && finding.status === 'open' && (
            <button
              onClick={() => onAcknowledge(finding)}
              className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/40 hover:text-[var(--color-brand-accent)] motion-safe:transition-colors"
            >
              Acknowledge
            </button>
          )}
          {isActive && (
            <button
              onClick={() => onCreateCase(finding)}
              className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/50 hover:text-[var(--color-brand-accent)] motion-safe:transition-colors"
            >
              Create case
            </button>
          )}
          {isActive && canResolve && (
            <button
              onClick={() => onResolve(finding)}
              className="rounded-lg bg-[var(--color-brand-accent)] px-2.5 py-1.5 text-xs font-medium text-white hover:bg-[var(--color-brand-accent-hover)] motion-safe:transition-colors"
            >
              Resolve
            </button>
          )}
          {drill && (
            <button
              onClick={() => navigate(drill!)}
              aria-label={`Open ${drill}`}
              className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/40 hover:text-[var(--color-brand-accent)] motion-safe:transition-colors"
            >
              Open
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Config panel ──────────────────────────────────────────────────────

function ConfigPanel({
  configs,
  canEdit,
  onToggle,
  onSaveThresholds,
}: {
  configs: RuleConfig[]
  canEdit: boolean
  onToggle: (code: string, enabled: boolean) => void
  onSaveThresholds: (code: string, thresholds: Record<string, unknown>) => void
}) {
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const grouped = useMemo(() => {
    const map: Record<string, RuleConfig[]> = {}
    for (const c of configs) {
      map[c.category] = map[c.category] || []
      map[c.category].push(c)
    }
    return map
  }, [configs])

  return (
    <Card title="Rule Configuration" subtitle="Deterministic thresholds per rule — auditable">
      {errorMsg && (
        <div className="mb-4 rounded-lg border border-[var(--color-danger)]/25 bg-[var(--color-danger)]/5 px-3 py-2 text-xs text-[var(--color-danger)]" role="alert">
          {errorMsg}
        </div>
      )}
      {configs.length === 0 ? (
        <p className="text-sm text-[var(--color-text-tertiary)] py-4 text-center">No rules configured.</p>
      ) : (
        <div className="space-y-5">
          {Object.entries(grouped).map(([category, rules]) => (
            <div key={category}>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)] mb-2">
                {CATEGORY_LABELS[category] || category}
              </p>
              <div className="space-y-2">
                {rules.map((rule) => {
                  const thresholdKeys = Object.keys(rule.thresholds || {}).filter((k) => !k.startsWith('required_categories'))
                  return (
                    <div key={rule.rule_code} className="rounded-xl border border-[var(--color-border)] p-3.5">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-[var(--color-text-primary)]">{rule.name}</p>
                          <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">{rule.description}</p>
                        </div>
                        <label className="flex items-center gap-2 cursor-pointer select-none">
                          <span className={cn('text-xs font-medium', rule.enabled ? 'text-[var(--color-success)]' : 'text-[var(--color-text-muted)]')}>
                            {rule.enabled ? 'On' : 'Off'}
                          </span>
                          <button
                            role="switch"
                            aria-checked={rule.enabled}
                            aria-label={`Toggle ${rule.name}`}
                            disabled={!canEdit}
                            onClick={() => onToggle(rule.rule_code, !rule.enabled)}
                            className={cn(
                              'relative h-5 w-9 rounded-full motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)]',
                              rule.enabled ? 'bg-[var(--color-brand-accent)]' : 'bg-[var(--color-border)]',
                              !canEdit && 'opacity-60 cursor-not-allowed'
                            )}
                          >
                            <span
                              className={cn(
                                'absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow motion-safe:transition-transform motion-safe:duration-[var(--motion-fast)]',
                                rule.enabled && 'translate-x-4'
                              )}
                            />
                          </button>
                        </label>
                      </div>

                      {canEdit && thresholdKeys.length > 0 && (
                        <div className="mt-3 flex items-end gap-2">
                          <div className="flex-1">
                            <label className="text-[11px] text-[var(--color-text-tertiary)] block mb-1">
                              Thresholds ({thresholdKeys.join(', ')})
                            </label>
                            <input
                              value={drafts[rule.rule_code] ?? JSON.stringify(rule.thresholds)}
                              onChange={(e) => {
                                setDrafts((d) => ({ ...d, [rule.rule_code]: e.target.value }))
                                setErrorMsg(null)
                              }}
                              className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1.5 text-xs font-mono text-[var(--color-text-primary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
                              placeholder='{"min_percentage": 75}'
                              aria-label={`Thresholds JSON for ${rule.name}`}
                            />
                          </div>
                          <button
                            onClick={async () => {
                              const raw = drafts[rule.rule_code] ?? JSON.stringify(rule.thresholds)
                              let parsed: Record<string, unknown>
                              try {
                                parsed = JSON.parse(raw) as Record<string, unknown>
                              } catch {
                                setErrorMsg(`Invalid JSON in ${rule.name} thresholds`)
                                return
                              }
                              setSaving(rule.rule_code)
                              try {
                                await onSaveThresholds(rule.rule_code, parsed)
                                setDrafts((d) => {
                                  const next = { ...d }
                                  delete next[rule.rule_code]
                                  return next
                                })
                              } catch {
                                // parent handler already toasts the error
                              } finally {
                                setSaving(null)
                              }
                            }}
                            disabled={saving === rule.rule_code}
                            className="rounded-lg bg-[var(--color-brand-accent)] px-3 py-1.5 text-xs font-medium text-white hover:bg-[var(--color-brand-accent-hover)] motion-safe:transition-colors disabled:opacity-60"
                          >
                            {saving === rule.rule_code ? 'Saving…' : 'Save'}
                          </button>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

// ── Skeletons ─────────────────────────────────────────────────────────

function RiskCenterSkeleton() {
  return (
    <div className="space-y-8 animate-fade-in" aria-busy="true" aria-label="Loading risk center">
      <div className="space-y-3">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96" />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-20 rounded-2xl" />
        ))}
      </div>
      <div className="space-y-2">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-24 rounded-xl" />
        ))}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────

export function RiskCenterPage() {
  const { user } = useAuth()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const role = (user?.role as string) || 'staff'
  const canResolve = ['admin', 'principal'].includes(role)
  const canAcknowledge = ['admin', 'principal', 'staff'].includes(role)
  const canEditConfig = role === 'admin'
  const canRecompute = ['admin', 'principal'].includes(role)

  const [overview, setOverview] = useState<RiskOverview | null>(null)
  const [findings, setFindings] = useState<RiskFindingPage | null>(null)
  const [configs, setConfigs] = useState<RuleConfig[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [category, setCategory] = useState<string>('')
  const [severity, setSeverity] = useState<string>('')
  const [statusFilter, setStatusFilter] = useState<string>('open')
  const [page, setPage] = useState(1)
  const [showConfig, setShowConfig] = useState(false)

  const [recomputing, setRecomputing] = useState(false)
  const [recomputeResult, setRecomputeResult] = useState<RecomputeResult | null>(null)
  const [resolveTarget, setResolveTarget] = useState<RiskFinding | null>(null)
  const [resolveReason, setResolveReason] = useState('')
  const [busyId, setBusyId] = useState<number | null>(null)
  const [caseCreatingId, setCaseCreatingId] = useState<number | null>(null)
  const fetchIdRef = useRef(0)

  const loadFindings = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    try {
      const data = await riskApi.listFindings({
        category: category || null,
        severity: severity || null,
        status: statusFilter || null,
        page,
        size: 20,
      })
      if (fetchId === fetchIdRef.current) setFindings(data)
    } catch (err: any) {
      // Keep last-good data on filter failures — never nuke the page.
      if (fetchId === fetchIdRef.current) {
        showToast(err?.detail || 'Failed to load findings', 'error')
      }
    }
  }, [category, severity, statusFilter, page, showToast])

  useEffect(() => {
    setLoading(true)
    setError(null)
    Promise.allSettled([riskApi.getOverview(), riskApi.listFindings({ status: 'open', size: 20 }), riskApi.getConfig()])
      .then(([ov, fd, cfg]) => {
        if (ov.status === 'fulfilled') setOverview(ov.value)
        if (fd.status === 'fulfilled') setFindings(fd.value)
        if (cfg.status === 'fulfilled') setConfigs(cfg.value)
        // Only treat it as a hard failure if every data source is down.
        if (ov.status === 'rejected' && fd.status === 'rejected' && cfg.status === 'rejected') {
          setError('Failed to load the Risk Center')
        }
        setLoading(false)
      })
  }, [])

  // Re-fetch findings whenever filters/page change after the initial load
  const firstLoadDone = useRef(false)
  useEffect(() => {
    if (!firstLoadDone.current) {
      firstLoadDone.current = true
      return
    }
    loadFindings()
  }, [loadFindings])

  const handleRecompute = async () => {
    setRecomputing(true)
    setRecomputeResult(null)
    try {
      const result = await riskApi.recompute()
      setRecomputeResult(result)
      showToast(`Recomputed: ${result.created} new, ${result.updated} updated, ${result.resolved} resolved`, 'success')
      // Refresh all sections
      const [ov, fd] = await Promise.all([
        riskApi.getOverview(),
        riskApi.listFindings({ status: statusFilter || null, page, size: 20 }),
      ])
      setOverview(ov)
      setFindings(fd)
    } catch (err: any) {
      showToast(err?.detail || 'Recompute failed', 'error')
    } finally {
      setRecomputing(false)
    }
  }

  const handleToggle = async (code: string, enabled: boolean) => {
    try {
      const updated = await riskApi.updateConfig(code, { enabled })
      setConfigs((prev) => prev?.map((c) => (c.rule_code === code ? updated : c)) ?? null)
      showToast(`Rule ${enabled ? 'enabled' : 'disabled'}`, 'success')
    } catch (err: any) {
      showToast(err?.detail || 'Update failed', 'error')
    }
  }

  const handleSaveThresholds = async (code: string, thresholds: Record<string, unknown>) => {
    try {
      const updated = await riskApi.updateConfig(code, { thresholds })
      setConfigs((prev) => prev?.map((c) => (c.rule_code === code ? updated : c)) ?? null)
      showToast('Thresholds saved', 'success')
    } catch (err: any) {
      showToast(err?.detail || 'Update failed', 'error')
    }
  }

  const handleAcknowledge = async (f: RiskFinding) => {
    setBusyId(f.id)
    try {
      const updated = await riskApi.acknowledgeFinding(f.id)
      setFindings((prev) =>
        prev ? { ...prev, items: prev.items.map((i) => (i.id === f.id ? updated : i)) } : prev
      )
      showToast('Finding acknowledged', 'success')
    } catch (err: any) {
      showToast(err?.detail || 'Acknowledge failed', 'error')
    } finally {
      setBusyId(null)
    }
  }

  const handleResolve = async () => {
    if (!resolveTarget) return
    setBusyId(resolveTarget.id)
    try {
      const updated = await riskApi.resolveFinding(resolveTarget.id, resolveReason.trim() || 'Resolved by staff')
      setFindings((prev) =>
        prev ? { ...prev, items: prev.items.map((i) => (i.id === resolveTarget.id ? updated : i)) } : prev
      )
      showToast('Finding resolved (audited)', 'success')
      setResolveTarget(null)
      setResolveReason('')
    } catch (err: any) {
      showToast(err?.detail || 'Resolve failed', 'error')
    } finally {
      setBusyId(null)
    }
  }

  // P8 §13 — promote an open risk finding into an operational case. The case
  // references the finding via source_type/source_id; the finding itself is
  // not mutated, keeping the risk audit trail intact.
  const handleCreateCase = async (f: RiskFinding) => {
    setCaseCreatingId(f.id)
    try {
      const c = await casesApi.create({
        title: f.reason || `Risk finding #${f.id}`,
        description: `Risk finding #${f.id} (${f.category}) — ${f.recommended_action || 'requires attention'}`,
        case_type: f.category === 'finance' ? 'finance'
          : f.category === 'attendance' ? 'attendance'
          : f.category === 'academic' ? 'academic'
          : f.category === 'documents' ? 'documents'
          : f.category === 'admissions' ? 'admissions'
          : 'operational',
        priority: f.severity as CasePriority,
        source_type: 'risk_finding',
        source_id: f.id,
        student_id: f.student_id,
      })
      showToast(`Case ${c.case_number} created from finding #${f.id}`, 'success')
      navigate(`/cases/${c.id}`)
    } catch (err: any) {
      showToast(err?.detail || 'Could not create case', 'error')
    } finally {
      setCaseCreatingId(null)
    }
  }

  const overviewCards = overview
    ? SEVERITY_ORDER.map((s) => ({ key: s, label: s, value: overview[s] }))
    : []

  const visibleFindings = findings?.items ?? []

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[var(--color-brand-navy)] via-[var(--color-brand-navy-light)] to-[var(--color-brand-navy-mid)] p-7 lg:p-8">
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage:
              'linear-gradient(rgba(255,255,255,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.3) 1px, transparent 1px)',
            backgroundSize: '40px 40px',
          }}
        />
        <div className="relative">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
            <div className="space-y-1.5">
              <p className="text-sm font-medium text-[var(--color-brand-accent)] tracking-wide">Deterministic · Explainable · Auditable</p>
              <h1 className="text-2xl lg:text-3xl font-extrabold text-white leading-tight tracking-tight">Risk &amp; Attention Engine</h1>
              <p className="text-white/50 text-sm max-w-xl leading-relaxed">
                Rule-based findings across attendance, finance, academics, documents, admissions and operations.
              </p>
            </div>
            <div className="flex items-center gap-2">
              {recomputeResult && (
                <span className="text-xs text-white/60 mr-1">
                  {recomputeResult.created} new · {recomputeResult.resolved} resolved
                </span>
              )}
              {canRecompute && (
                <button
                  onClick={handleRecompute}
                  disabled={recomputing}
                  className={cn(
                    'inline-flex items-center gap-2 rounded-xl bg-[var(--color-brand-accent)] px-4 py-2 text-sm font-medium text-white',
                    'hover:bg-[var(--color-brand-accent-hover)] motion-safe:transition-colors shadow-lg shadow-[var(--color-brand-accent)]/20',
                    recomputing && 'opacity-60 cursor-wait'
                  )}
                >
                  <svg className={cn('h-4 w-4', recomputing && 'animate-spin')} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  {recomputing ? 'Running…' : 'Run Rules'}
                </button>
              )}
              <button
                onClick={() => setShowConfig((v) => !v)}
                className="inline-flex items-center gap-2 rounded-xl bg-white/10 px-4 py-2 text-sm font-medium text-white hover:bg-white/20 motion-safe:transition-colors"
              >
                {showConfig ? 'Hide' : 'Configure'} Rules
              </button>
            </div>
          </div>
        </div>
      </div>

      {loading ? (
        <RiskCenterSkeleton />
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-16 text-center animate-fade-in">
          <div className="h-14 w-14 rounded-2xl bg-[var(--color-danger-light)] flex items-center justify-center mb-5">
            <svg className="h-7 w-7 text-[var(--color-danger)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <h3 className="text-sm font-semibold text-[var(--color-danger-dark)]">{error}</h3>
          <button
            onClick={() => window.location.reload()}
            className="mt-5 inline-flex items-center rounded-[10px] bg-[var(--color-danger)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--color-danger-dark)] motion-safe:transition-colors"
          >
            Try Again
          </button>
        </div>
      ) : (
        <>
          {/* Overview cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {overviewCards.map((c) => (
              <SeverityCard key={c.key} label={`${c.label} risk`} value={c.value} tone={c.key} />
            ))}
          </div>

          {/* Category breakdown */}
          {overview && Object.keys(overview.by_category).length > 0 && (
            <div className="flex flex-wrap gap-2">
              {Object.entries(overview.by_category).map(([cat, count]) => (
                <button
                  key={cat}
                  onClick={() => {
                    setCategory(cat === category ? '' : cat)
                    setPage(1)
                  }}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium motion-safe:transition-colors',
                    cat === category
                      ? 'border-[var(--color-brand-accent)] bg-[var(--color-brand-accent)]/10 text-[var(--color-brand-accent)]'
                      : 'border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/40'
                  )}
                >
                  {CATEGORY_LABELS[cat] || cat}
                  <span className="tabular-nums">{count}</span>
                </button>
              ))}
            </div>
          )}

          {/* Config panel */}
          {showConfig && configs && (
            <ConfigPanel
              configs={configs}
              canEdit={canEditConfig}
              onToggle={handleToggle}
              onSaveThresholds={handleSaveThresholds}
            />
          )}

          {/* Findings */}
          <section>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
              <div>
                <h2 className="text-base font-semibold text-[var(--color-text-primary)]">Findings</h2>
                <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">
                  {findings ? `${findings.total} total` : ''} · Rules never claim predictive intelligence
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={category}
                  onChange={(e) => { setCategory(e.target.value); setPage(1) }}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1.5 text-xs text-[var(--color-text-secondary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
                  aria-label="Filter by category"
                >
                  <option value="">All categories</option>
                  {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
                <select
                  value={severity}
                  onChange={(e) => { setSeverity(e.target.value); setPage(1) }}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1.5 text-xs text-[var(--color-text-secondary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
                  aria-label="Filter by severity"
                >
                  <option value="">All severities</option>
                  {SEVERITY_ORDER.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <select
                  value={statusFilter}
                  onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1.5 text-xs text-[var(--color-text-secondary)] focus:border-[var(--color-brand-accent)] focus:outline-none"
                  aria-label="Filter by status"
                >
                  {STATUS_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {visibleFindings.length === 0 ? (
              <div className="rounded-2xl border border-[var(--color-success)]/20 bg-[var(--color-success)]/5 p-8 text-center">
                <p className="text-sm font-semibold text-[var(--color-success-dark)]">No findings</p>
                <p className="text-xs text-[var(--color-success)]/70 mt-1">
                  {statusFilter === 'open' ? 'No open risk findings for this view.' : 'No findings match the current filters.'}
                </p>
              </div>
            ) : (
              <div className="space-y-2.5">
                {visibleFindings.map((f, i) => (
                  <FindingCard
                    key={f.id}
                    finding={f}
                    index={i}
                    canResolve={canResolve}
                    canAcknowledge={canAcknowledge}
                    onResolve={setResolveTarget}
                    onAcknowledge={handleAcknowledge}
                    onCreateCase={handleCreateCase}
                  />
                ))}
              </div>
            )}

            {/* Pagination */}
            {findings && findings.pages > 1 && (
              <div className="flex items-center justify-center gap-3 mt-6">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/40 disabled:opacity-40"
                >
                  Previous
                </button>
                <span className="text-xs text-[var(--color-text-tertiary)]">
                  Page {findings.page} of {findings.pages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(findings.pages, p + 1))}
                  disabled={page >= findings.pages}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:border-[var(--color-brand-accent)]/40 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            )}
          </section>
        </>
      )}

      {/* Resolve dialog — audited resolution with mandatory reason */}
      <Modal
        open={!!resolveTarget}
        onClose={() => setResolveTarget(null)}
        title="Resolve finding"
        size="sm"
        footer={
          <>
            <Button variant="outline" size="sm" onClick={() => setResolveTarget(null)}>Cancel</Button>
            <Button size="sm" onClick={handleResolve} disabled={busyId === resolveTarget?.id}>
              {busyId === resolveTarget?.id ? 'Resolving…' : 'Resolve'}
            </Button>
          </>
        }
      >
        <p className="text-xs text-[var(--color-text-tertiary)]">{resolveTarget?.reason}</p>
        <textarea
          value={resolveReason}
          onChange={(e) => setResolveReason(e.target.value)}
          placeholder="Reason (audited) — e.g. fees paid in cash, parent contacted"
          rows={3}
          className="mt-4 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-brand-accent)] focus:outline-none resize-none"
        />
      </Modal>

    </div>
  )
}

export default RiskCenterPage
