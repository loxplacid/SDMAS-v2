import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  MIGRATION_STATUS_LABELS,
  MIGRATION_STATUS_STYLES,
  SOURCE_SYSTEMS,
  migrationApi,
  type MappingEntry,
  type MigrationProject,
  type PreviewRow,
} from '../../api/migration/migration-api'
import {
  Badge,
  Button,
  EmptyState,
  Input,
  PageHeader,
  Select,
  Skeleton,
  Alert,
  ConfirmDialog,
} from '../../components/ui'
import { useToast } from '../../components/ui/toast'
import { cn, formatDateTime, plural } from '../../lib/utils'

// ── Steps ─────────────────────────────────────────────────────────────

const STEPS = ['Source', 'Mapping', 'Validate & Preview', 'Import', 'Reconcile & Report']

function statusToStep(status: MigrationProject['status']): number {
  switch (status) {
    case 'DRAFT':
    case 'DISCOVERING':
      return 0
    case 'MAPPING':
      return 1
    case 'VALIDATING':
    case 'READY':
      return 2
    case 'IMPORTING':
    case 'RECONCILING':
      return 3
    default:
      return 4
  }
}

function Stepper({ current }: { current: number }) {
  return (
    <ol className="flex items-center gap-2 flex-wrap" aria-label="Migration steps">
      {STEPS.map((label, i) => {
        const done = i < current
        const active = i === current
        return (
          <li key={label} className="flex items-center gap-2">
            <span
              className={cn(
                'flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium',
                done && 'bg-[var(--color-success)]/10 text-[var(--color-success)]',
                active && 'bg-[var(--color-brand-accent)]/15 text-[var(--color-brand-accent)] ring-1 ring-[var(--color-brand-accent)]/30',
                !done && !active && 'bg-[var(--color-surface-muted)] text-[var(--color-text-tertiary)]'
              )}
            >
              <span
                className={cn(
                  'h-4 w-4 rounded-full text-[10px] leading-4 text-center font-bold',
                  done && 'bg-[var(--color-success)] text-white',
                  active && 'bg-[var(--color-brand-accent)] text-white',
                  !done && !active && 'bg-[var(--color-border)] text-[var(--color-text-tertiary)]'
                )}
              >
                {done ? '✓' : i + 1}
              </span>
              {label}
            </span>
            {i < STEPS.length - 1 && (
              <span className="h-px w-4 bg-[var(--color-border)]" aria-hidden="true" />
            )}
          </li>
        )
      })}
    </ol>
  )
}

// ── Step 1: Source ────────────────────────────────────────────────────

function SourceStep({ onCreated }: { onCreated: (p: MigrationProject) => void }) {
  const { showToast } = useToast()
  const [name, setName] = useState('')
  const [sourceSystem, setSourceSystem] = useState(SOURCE_SYSTEMS[0])
  const [description, setDescription] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canSubmit = name.trim() && file

  const submit = async () => {
    if (!canSubmit || !file) return
    setSubmitting(true)
    setError(null)
    try {
      const project = await migrationApi.create(
        { name: name.trim(), source_system: sourceSystem, description: description.trim() || undefined },
        file
      )
      showToast(`Source discovered — ${project.row_count} records`, 'success')
      onCreated(project)
    } catch (e: any) {
      setError(e?.detail || 'Upload failed. Check the file and try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
      <div className="lg:col-span-3 space-y-4">
        <Input label="Migration name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. 2026 PowerSchool export" required />
        <Select
          label="Source system"
          value={sourceSystem}
          onChange={(e) => setSourceSystem(e.target.value)}
          options={SOURCE_SYSTEMS.map((s) => ({ value: s, label: s }))}
        />
        <Input label="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What is this export and where did it come from?" />
        <div>
          <p className="text-xs font-medium text-[var(--color-text-muted)] mb-1.5">Source file</p>
          <label className="block rounded-xl border border-dashed border-[var(--color-border)] p-6 text-center cursor-pointer hover:border-[var(--color-brand-accent)]/40 motion-safe:transition-colors">
            <input
              type="file"
              accept=".csv,.xlsx,.json,.jsonl,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              className="sr-only"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            <p className="text-sm font-medium text-[var(--color-text-primary)]">
              {file ? file.name : 'Choose a CSV, XLSX, JSON or JSONL export'}
            </p>
            <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
              {file ? `${(file.size / 1024).toFixed(1)} KB` : 'We will discover columns, types and field mappings automatically.'}
            </p>
          </label>
        </div>
        {error && <Alert variant="error">{error}</Alert>}
        <div className="flex justify-end">
          <Button onClick={submit} disabled={!canSubmit || submitting} loading={submitting}>
            Upload & discover
          </Button>
        </div>
      </div>
      <div className="lg:col-span-2">
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-sm text-[var(--color-text-muted)] space-y-2.5">
          <p className="font-semibold text-[var(--color-text-primary)]">What happens next</p>
          <ul className="space-y-2 list-disc pl-4">
            <li>We inspect every column and infer its type, null rate and role.</li>
            <li>Deterministic heuristics suggest which legacy fields map to SDMAS fields — each with a confidence and reason.</li>
            <li>You confirm or correct the mapping and review transformations before anything touches the database.</li>
            <li>Validation blocks the import while required fields are missing or malformed.</li>
            <li>The import runs in the background — you can leave and come back; progress is stored server-side.</li>
          </ul>
        </div>
      </div>
    </div>
  )
}

// ── Step 2: Mapping ───────────────────────────────────────────────────

interface ColumnProfile {
  name: string
  inferred_type: string
  null_rate: number
  distinct_ratio: number
  is_duplicate_candidate: boolean
  sample_values: string[]
  looks_like_date?: boolean
  looks_like_email?: boolean
  looks_like_phone?: boolean
  looks_like_identifier?: boolean
}

//: Targets are grouped by entity so the operator can see which streams
//: (students / academic / attendance / fees) a mapping will produce.
const TARGET_OPTIONS = [
  { value: '', label: '— Not mapped —' },
  { value: 'student_number', label: 'Student Number (required)' },
  { value: 'first_name', label: 'First Name (required)' },
  { value: 'last_name', label: 'Last Name (required)' },
  { value: 'full_name', label: 'Full Name → split first/last' },
  { value: 'email', label: 'Email' },
  { value: 'date_of_birth', label: 'Date of Birth' },
  { value: 'gender', label: 'Gender' },
  { value: 'status', label: 'Status' },
  { value: 'guardian_phone', label: 'Guardian Phone' },
  { value: 'class_name', label: 'Class / Grade (academic)' },
  { value: 'section_name', label: 'Section (academic)' },
  { value: 'academic_year_name', label: 'Academic Year (academic)' },
  { value: 'attendance_date', label: 'Attendance Date (attendance)' },
  { value: 'attendance_status', label: 'Attendance Status (attendance)' },
  { value: 'amount_paid', label: 'Amount Paid (finance)' },
  { value: 'fee_type_name', label: 'Fee Type (finance)' },
  { value: 'payment_date', label: 'Payment Date (finance)' },
  { value: 'receipt_no', label: 'Receipt Number (finance)' },
]

const TRANSFORM_OPTIONS = [
  { value: 'trim', label: 'Trim' },
  { value: 'lowercase', label: 'Lowercase' },
  { value: 'uppercase', label: 'Uppercase' },
  { value: 'normalize_email', label: 'Normalize email' },
  { value: 'normalize_phone', label: 'Normalize phone' },
  { value: 'parse_date', label: 'Parse date' },
  { value: 'map_values', label: 'Map values' },
  { value: 'split_name', label: 'Split name' },
  { value: 'default', label: 'Default missing' },
  { value: 'replace', label: 'Replace' },
  { value: 'strip_prefix', label: 'Strip prefix' },
]

const CONFIDENCE_BADGE: Record<string, 'success' | 'info' | 'neutral'> = {
  high: 'success',
  medium: 'info',
  low: 'neutral',
}

const ENTITY_LABELS: Record<string, string> = {
  students: 'Students',
  academic: 'Academic structure',
  attendance: 'Attendance',
  fees: 'Fees / finance',
}

const ACTION_BADGE: Record<string, 'success' | 'info' | 'warning' | 'danger' | 'neutral'> = {
  CREATE: 'success',
  UPDATE: 'info',
  SKIP: 'neutral',
  ERROR: 'danger',
}

function MappingStep({
  project,
  onSaved,
}: {
  project: MigrationProject
  onSaved: (p: MigrationProject) => void
}) {
  const { showToast } = useToast()
  const [mapping, setMapping] = useState<Record<string, MappingEntry>>(project.mapping || {})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const columns = useMemo<ColumnProfile[]>(
    () => (project.discovery?.columns as unknown as ColumnProfile[]) || [],
    [project.discovery]
  )
  const suggestions = project.discovery?.suggestions || []

  useEffect(() => setMapping(project.mapping || {}), [project.mapping])

  const setTarget = (source: string, target: string) => {
    setMapping((prev) => {
      const next = { ...prev }
      const existing = next[source]
      const suggestion = suggestions.find((s) => s.source_field === source)
      if (!target) {
        delete next[source]
      } else {
        next[source] = {
          target,
          confidence: existing?.confidence || suggestion?.confidence || 'medium',
          reason: existing?.reason || suggestion?.reason || 'Manual selection',
          transforms: existing?.transforms || [],
        }
      }
      return next
    })
  }

  const toggleTransform = (source: string, op: string) => {
    setMapping((prev) => {
      const next = { ...prev }
      const entry = next[source]
      if (!entry) return prev
      const transforms = entry.transforms || []
      const has = transforms.some((t) => t.op === op)
      next[source] = {
        ...entry,
        transforms: has ? transforms.filter((t) => t.op !== op) : [...transforms, { op }],
      }
      return next
    })
  }

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      const updated = await migrationApi.saveMapping(project.id, mapping)
      showToast('Mapping saved', 'success')
      onSaved(updated)
    } catch (e: any) {
      setError(e?.detail || 'Could not save mapping')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">Field mapping</h2>
          <p className="text-xs text-[var(--color-text-tertiary)]">
            Confirm how each legacy column maps into SDMAS. Required fields are marked; the import is blocked until they are mapped.
          </p>
          {/* Detected entity streams (Step 2) — the mapping below drives
              which migrators run at import time. */}
          {(project.discovery?.entities?.length ?? 0) > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 mt-2">
              <span className="text-[11px] text-[var(--color-text-tertiary)]">Will import:</span>
              {project.discovery!.entities.map((entity) => (
                <Badge key={entity} variant="info" size="sm">
                  {ENTITY_LABELS[entity] || entity}
                </Badge>
              ))}
            </div>
          )}
        </div>
        <Button onClick={save} disabled={saving} loading={saving}>Save mapping</Button>
      </div>
      {error && <Alert variant="error">{error}</Alert>}

      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-left text-[11px] uppercase tracking-wider text-[var(--color-text-tertiary)]">
                <th className="px-4 py-3 font-semibold">Legacy column</th>
                <th className="px-4 py-3 font-semibold">Profile</th>
                <th className="px-4 py-3 font-semibold w-56">SDMAS target</th>
                <th className="px-4 py-3 font-semibold">Confidence</th>
                <th className="px-4 py-3 font-semibold">Transforms</th>
              </tr>
            </thead>
            <tbody>
              {columns.map((col) => {
                const entry = mapping[col.name]
                const isMapped = !!entry?.target
                const isRequired = ['student_number', 'first_name', 'last_name'].includes(entry?.target || '')
                return (
                  <tr key={col.name} className="border-b border-[var(--color-border)]/60 last:border-0 align-top">
                    <td className="px-4 py-3">
                      <p className="font-medium text-[var(--color-text-primary)]">{col.name}</p>
                      {isRequired && (
                        <Badge variant="warning" size="sm" className="mt-1">required</Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-[var(--color-text-muted)]">
                      <p>{col.inferred_type}{col.looks_like_date ? ' · date' : ''}{col.looks_like_email ? ' · email' : ''}{col.looks_like_phone ? ' · phone' : ''}</p>
                      <p className="text-[var(--color-text-tertiary)]">
                        {Math.round((1 - col.null_rate) * 100)}% populated ·{' '}
                        {col.is_duplicate_candidate ? 'duplicate candidate' : `${Math.round(col.distinct_ratio * 100)}% distinct`}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={entry?.target || ''}
                        onChange={(e) => setTarget(col.name, e.target.value)}
                        className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1.5 text-sm focus:border-[var(--color-brand-accent)] focus:outline-none"
                        aria-label={`Map ${col.name}`}
                      >
                        {TARGET_OPTIONS.map((o) => (
                          <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                      </select>
                      {isMapped && entry.reason && (
                        <p className="text-[10px] text-[var(--color-text-tertiary)] mt-1">{entry.reason}</p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={CONFIDENCE_BADGE[entry?.confidence || 'medium'] || 'neutral'} size="sm">
                        {entry?.confidence || '—'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      {isMapped ? (
                        <div className="flex flex-wrap gap-1.5 max-w-xs">
                          {TRANSFORM_OPTIONS.map((t) => {
                            const active = (entry.transforms || []).some((x) => x.op === t.value)
                            return (
                              <button
                                key={t.value}
                                onClick={() => toggleTransform(col.name, t.value)}
                                title={t.label}
                                className={cn(
                                  'rounded-full px-2 py-0.5 text-[10px] font-medium border motion-safe:transition-colors',
                                  active
                                    ? 'border-[var(--color-brand-accent)]/40 bg-[var(--color-brand-accent)]/15 text-[var(--color-brand-accent)]'
                                    : 'border-[var(--color-border)] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]'
                                )}
                              >
                                {t.label}
                              </button>
                            )
                          })}
                        </div>
                      ) : (
                        <span className="text-xs text-[var(--color-text-tertiary)]">Unmapped</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// ── Step 3: Validate + Preview ────────────────────────────────────────

function ValidateStep({
  project,
  onValidated,
}: {
  project: MigrationProject
  onValidated: (p: MigrationProject) => void
}) {
  const { showToast } = useToast()
  const [running, setRunning] = useState(false)
  const [preview, setPreview] = useState<PreviewRow[]>([])
  const [previewLoading, setPreviewLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const validation = project.validation

  const runValidation = async () => {
    setRunning(true)
    setError(null)
    try {
      const result = await migrationApi.validate(project.id)
      showToast(
        result.is_ready
          ? `${result.total} records valid — ready to import`
          : `${result.blocking} blocking issue(s) found`,
        result.is_ready ? 'success' : 'warning'
      )
      onValidated({ ...project, validation: result })
    } catch (e: any) {
      setError(e?.detail || 'Validation failed')
    } finally {
      setRunning(false)
    }
  }

  const loadPreview = async () => {
    setPreviewLoading(true)
    try {
      const result = await migrationApi.preview(project.id, 5)
      setPreview(result.rows)
    } catch {
      setPreview([])
    } finally {
      setPreviewLoading(false)
    }
  }

  useEffect(() => {
    if (project.status === 'READY' || project.status === 'VALIDATING') loadPreview()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id])

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">Validate & preview</h2>
          <p className="text-xs text-[var(--color-text-tertiary)]">
            The import stays blocked while blocking errors exist. Preview shows original → transformed values.
          </p>
        </div>
        <Button onClick={runValidation} disabled={running} loading={running}>
          {validation ? 'Re-run validation' : 'Run validation'}
        </Button>
      </div>
      {error && <Alert variant="error">{error}</Alert>}

      {validation && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Total', value: validation.total, color: 'text-[var(--color-text-primary)]' },
            { label: 'Blocking', value: validation.blocking, color: validation.blocking > 0 ? 'text-[var(--color-danger)]' : 'text-[var(--color-success)]' },
            { label: 'Warnings', value: validation.warnings, color: 'text-[var(--color-warning)]' },
            { label: 'Ready', value: validation.is_ready ? 'Yes' : 'No', color: validation.is_ready ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]' },
          ].map((item) => (             <div key={item.label} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
              <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)]">{item.label}</p>
              <p className={cn('mt-1.5 text-2xl font-bold tabular-nums leading-none', item.color)}>{item.value}</p>
            </div>
          ))}
        </div>
      )}

      {validation && Object.keys(validation.categories || {}).length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-[var(--color-text-tertiary)]">Issues by type:</span>
          {Object.entries(validation.categories).map(([category, count]) => (
            <Badge key={category} variant="neutral" size="sm" className="tabular-nums">
              {category.replace(/_/g, ' ')} · {count}
            </Badge>
          ))}
        </div>
      )}

      {validation && validation.samples.length > 0 && (
        <div className="rounded-xl border border-[var(--color-danger)]/30 bg-[var(--color-danger)]/5 p-4">
          <p className="text-xs font-semibold text-[var(--color-danger)] mb-2">Blocking issues (first {validation.samples.length})</p>
          <ul className="space-y-1.5 text-xs text-[var(--color-text-muted)]">
            {validation.samples.slice(0, 8).map((sample: any, i) => (
              <li key={i} className="flex gap-2">
                <span className="tabular-nums text-[var(--color-text-tertiary)]">Row {sample.row}:</span>
                <span>{Array.isArray(sample.issues) ? sample.issues.join('; ') : 'Invalid record'}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)] mb-2">Before → after (sample)</h3>
        {previewLoading ? (
          <Skeleton className="h-32 rounded-xl" />
        ) : preview.length === 0 ? (
          <EmptyState compact title="No preview" description="Run validation to load the preview." />
        ) : (
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)] text-left text-[11px] uppercase tracking-wider text-[var(--color-text-tertiary)]">
                    <th className="px-4 py-2.5 font-semibold">Row</th>
                    <th className="px-4 py-2.5 font-semibold">Action</th>
                    <th className="px-4 py-2.5 font-semibold">Original</th>
                    <th className="px-4 py-2.5 font-semibold">Transformed</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.map((row) => (
                    <tr key={row.row} className="border-b border-[var(--color-border)]/60 last:border-0">
                      <td className="px-4 py-2.5 text-xs tabular-nums text-[var(--color-text-tertiary)]">{row.row}</td>
                      <td className="px-4 py-2.5">
                        <Badge variant={ACTION_BADGE[row.action] || 'neutral'} size="sm">
                          {row.action}
                        </Badge>
                        {row.action_reason && (
                          <p className="text-[10px] text-[var(--color-text-tertiary)] mt-1 max-w-56">{row.action_reason}</p>
                        )}
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex flex-wrap gap-1">
                          {Object.entries(row.before).slice(0, 5).map(([k, v]) => (
                            <span key={k} className="rounded bg-[var(--color-surface-muted)] px-1.5 py-0.5 text-[10px] text-[var(--color-text-muted)]">
                              {k}: {String(v ?? '')}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex flex-wrap gap-1">
                          {Object.entries(row.after).filter(([k]) => ['first_name', 'last_name', 'student_number', 'email', 'date_of_birth', 'status', 'gender'].includes(k)).map(([k, v]) => (
                            <span key={k} className="rounded bg-[var(--color-brand-accent)]/10 px-1.5 py-0.5 text-[10px] text-[var(--color-brand-accent)]">
                              {k}: {String(v ?? '')}
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Step 4: Import ────────────────────────────────────────────────────

function ImportStep({ project, onProgress }: { project: MigrationProject; onProgress: (p: MigrationProject) => void }) {
  const { showToast } = useToast()
  const [starting, setStarting] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const isRunning = project.status === 'IMPORTING' || project.status === 'RECONCILING'
  const pct =
    project.row_count > 0
      ? Math.min(100, Math.round((project.records_processed / project.row_count) * 100))
      : 0

  const poll = useCallback(async () => {
    try {
      const progress = await migrationApi.progress(project.id)
      onProgress({ ...project, ...progress } as MigrationProject)
    } catch {
      /* transient — keep polling */
    }
  }, [project.id, project, onProgress])

  useEffect(() => {
    if (isRunning) {
      pollRef.current = setTimeout(() => poll(), 2000)
      return () => {
        if (pollRef.current) clearTimeout(pollRef.current)
      }
    }
  }, [isRunning, poll, project.records_processed])

  const startImport = async () => {
    setStarting(true)
    setError(null)
    try {
      const updated = await migrationApi.startImport(project.id)
      showToast('Import started in the background', 'success')
      onProgress(updated)
    } catch (e: any) {
      setError(e?.detail || 'Could not start the import')
    } finally {
      setStarting(false)
    }
  }

  const cancel = async () => {
    setCancelling(true)
    try {
      const updated = await migrationApi.cancel(project.id)
      showToast('Import cancelled', 'warning')
      onProgress(updated)
    } catch (e: any) {
      showToast(e?.detail || 'Could not cancel', 'error')
    } finally {
      setCancelling(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">Background import</h2>
          <p className="text-xs text-[var(--color-text-tertiary)]">
            The import runs in the background and survives page refresh. Progress is tracked server-side.
          </p>
        </div>
        <div className="flex gap-2">
          {isRunning ? (
            <Button variant="secondary" onClick={cancel} disabled={cancelling} loading={cancelling}>Cancel</Button>
          ) : (
            <Button onClick={startImport} disabled={starting || project.status !== 'READY'} loading={starting}>
              Start import
            </Button>
          )}
        </div>
      </div>
      {error && <Alert variant="error">{error}</Alert>}
      {project.status !== 'READY' && !isRunning && (
        <Alert variant="warning">This migration is not ready to import. Resolve blocking issues in the validation step.</Alert>
      )}       <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 space-y-3">
        <div>
          <div className="flex justify-between text-xs text-[var(--color-text-muted)] mb-1.5">
            <span>{project.status === 'IMPORTING' ? 'Importing…' : project.status === 'RECONCILING' ? 'Reconciling…' : 'Not started'}</span>
            <span className="tabular-nums">{pct}%</span>
          </div>
          <div className="h-2 rounded-full bg-[var(--color-surface-muted)] overflow-hidden">
            <div
              className="h-full rounded-full bg-[var(--color-brand-accent)] motion-safe:transition-all motion-safe:duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          {[
            { label: 'Processed', value: project.records_processed, color: 'text-[var(--color-text-primary)]' },
            { label: 'Imported', value: project.records_imported, color: 'text-[var(--color-success)]' },
            { label: 'Skipped', value: project.records_skipped, color: 'text-[var(--color-warning)]' },
            { label: 'Rejected', value: project.records_rejected, color: project.records_rejected > 0 ? 'text-[var(--color-danger)]' : 'text-[var(--color-text-muted)]' },
          ].map((item) => (
            <div key={item.label} className="rounded-xl bg-[var(--color-surface-muted)] p-3">
              <p className="text-[11px] uppercase tracking-wider text-[var(--color-text-tertiary)]">{item.label}</p>
              <p className={cn('mt-1 text-xl font-bold tabular-nums', item.color)}>{item.value.toLocaleString()}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Step 5: Reconcile + Report ────────────────────────────────────────

function ReconcileStep({ project, onRolledBack }: { project: MigrationProject; onRolledBack: () => void }) {
  const { showToast } = useToast()
  const [reconciling, setReconciling] = useState(false)
  const [rollingBack, setRollingBack] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [rollbackConfirmOpen, setRollbackConfirmOpen] = useState(false)

  const [rec, setRec] = useState(project.reconciliation)
  useEffect(() => setRec(project.reconciliation), [project.reconciliation])

  const runReconcile = async () => {
    setReconciling(true)
    try {
      await migrationApi.reconcile(project.id)
      const fresh = await migrationApi.get(project.id)
      setRec(fresh.reconciliation)
      showToast('Reconciliation complete', 'success')
    } catch (e: any) {
      setError(e?.detail || 'Reconciliation failed')
    } finally {
      setReconciling(false)
    }
  }

  const downloadReport = async (format: 'txt' | 'csv' | 'json') => {
    setDownloading(true)
    try {
      const { blob, filename } = await migrationApi.reportBlob(project.id, format)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      showToast(e?.detail || 'Could not download report', 'error')
    } finally {
      setDownloading(false)
    }
  }

  const rollback = async () => {
    setRollingBack(true)
    try {
      const result = await migrationApi.rollback(project.id)
      showToast(`${result.records_removed} records rolled back`, 'success')
      onRolledBack()
    } catch (e: any) {
      setError(e?.detail || 'Rollback failed')
    } finally {
      setRollingBack(false)
      setRollbackConfirmOpen(false)
    }
  }

  const rows = rec
    ? [
        { label: 'Source records', value: rec.source_records, color: 'text-[var(--color-text-primary)]' },
        { label: 'Created', value: rec.created, color: 'text-[var(--color-success)]' },
        { label: 'Updated', value: rec.updated, color: 'text-[var(--color-text-muted)]' },
        { label: 'Skipped', value: rec.skipped, color: 'text-[var(--color-warning)]' },
        { label: 'Rejected', value: rec.rejected, color: rec.rejected > 0 ? 'text-[var(--color-danger)]' : 'text-[var(--color-text-muted)]' },
        { label: 'Duplicates', value: rec.duplicates, color: rec.duplicates > 0 ? 'text-[var(--color-warning)]' : 'text-[var(--color-text-muted)]' },
      ]
    : []

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">Reconciliation & report</h2>
          <p className="text-xs text-[var(--color-text-tertiary)]">
            Verify the totals reconcile before closing the migration. The report is downloadable and every step is audited.
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {!rec && (
            <Button onClick={runReconcile} disabled={reconciling} loading={reconciling}>Run reconciliation</Button>
          )}
          <span className="flex items-center gap-1.5">
            <span className="text-xs text-[var(--color-text-tertiary)]">Report:</span>
            <Button variant="secondary" size="sm" onClick={() => downloadReport('txt')} disabled={downloading}>TXT</Button>
            <Button variant="secondary" size="sm" onClick={() => downloadReport('csv')} disabled={downloading}>CSV</Button>
            <Button variant="secondary" size="sm" onClick={() => downloadReport('json')} disabled={downloading}>JSON</Button>
          </span>
          {project.status === 'COMPLETED' && (
            <Button variant="danger" onClick={() => setRollbackConfirmOpen(true)} disabled={rollingBack}>Roll back</Button>
          )}
        </div>
      </div>
      {error && <Alert variant="error">{error}</Alert>}

      {rec ? (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {rows.map((row) => (               <div key={row.label} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
                <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)]">{row.label}</p>
                <p className={cn('mt-1.5 text-2xl font-bold tabular-nums leading-none', row.color)}>{row.value.toLocaleString()}</p>
              </div>
            ))}
          </div>
          <div className="rounded-xl bg-[var(--color-surface-muted)] p-4 text-xs text-[var(--color-text-muted)]">
            <p>
              Reconciliation: source <strong className="tabular-nums">{rec.source_records}</strong> =
              created <strong className="tabular-nums">{rec.created}</strong> + updated{' '}
              <strong className="tabular-nums">{rec.updated}</strong> + skipped{' '}
              <strong className="tabular-nums">{rec.skipped}</strong> + rejected{' '}
              <strong className="tabular-nums">{rec.rejected}</strong>
            </p>
            <p className="mt-1">
              Reconciled at {formatDateTime(rec.reconciled_at)} · run #{rec.run_id} ({rec.run_status})
              {Array.isArray(rec.entities) && rec.entities.length > 0 && (
                <> · streams: {rec.entities.join(', ')}</>
              )}
            </p>
          </div>
        </>
      ) : (
        <EmptyState
          compact
          title="No reconciliation yet"
          description="Run reconciliation after the import completes to verify the totals."
        />
      )}

      <ConfirmDialog
        open={rollbackConfirmOpen}
        onClose={() => setRollbackConfirmOpen(false)}
        onConfirm={rollback}
        title="Roll Back Migration"
        message="Roll back all records created by this migration? Pre-existing records are never touched. This action cannot be undone."
        confirmLabel="Roll Back"
        variant="danger"
        loading={rollingBack}
      />
    </div>
  )
}

// ── Wizard shell ──────────────────────────────────────────────────────

export function MigrationWizardPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<MigrationProject | null>(null)
  const [loading, setLoading] = useState(Boolean(id))
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) {
      setProject(null)
      return
    }
    setLoading(true)
    setError(null)
    migrationApi
      .get(Number(id))
      .then(setProject)
      .catch((e: any) => setError(e?.detail || 'Migration could not be loaded.'))
      .finally(() => setLoading(false))
  }, [id])

  const step = project ? statusToStep(project.status) : 0

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-9 w-72" />
        <Skeleton className="h-5 w-96" />
        <Skeleton className="h-24 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    )
  }

  if (error) {
    return (
      <EmptyState
        icon={
          <svg className="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          </svg>
        }
        title="Migration couldn't be loaded"
        description={error}
        action={{ label: 'Back to migrations', onClick: () => navigate('/migration') }}
      />
    )
  }

  if (!project) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Administration"
          title="New data migration"
          subtitle="Start by uploading a legacy export — we will discover its structure and suggest a mapping."
          actions={<Button variant="secondary" onClick={() => navigate('/migration')}>Cancel</Button>}
        />
        <SourceStep onCreated={(p) => navigate(`/migration/${p.id}`)} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={project.source_system}
        title={project.name}
        subtitle={`${project.original_filename ?? 'No file'} · ${plural(project.row_count, 'record')} discovered · ${MIGRATION_STATUS_LABELS[project.status] || project.status}`}
        actions={<Button variant="secondary" onClick={() => navigate('/migration')}>All migrations</Button>}
      />

      <Stepper current={step} />

      {step === 0 && <SourceStep onCreated={(p) => setProject(p)} />}
      {step === 1 && <MappingStep project={project} onSaved={setProject} />}
      {step === 2 && <ValidateStep project={project} onValidated={setProject} />}
      {step === 3 && <ImportStep project={project} onProgress={setProject} />}
      {step >= 4 && <ReconcileStep project={project} onRolledBack={() => navigate('/migration')} />}
    </div>
  )
}
