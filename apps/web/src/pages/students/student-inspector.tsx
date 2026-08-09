import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { student360Api, type Student360Response } from '../../api/student-360/student-360-api'
import { Badge, Button } from '../../components/ui'
import { WorkspaceInspector } from '../../components/data-workspace'
import { usePermission } from '../../hooks/use-permission'
import { FEES_VIEW } from '../../types/permissions'
import { cn, formatDate } from '../../lib/utils'

/**
 * P9 — Student inspector: the contextual preview that opens from the Students
 * workspace (list → inspector). Desktop: right-side panel over the list.
 * Mobile: full-screen sheet.
 *
 * Reuses the existing 360 API (no new backend surface) and mirrors the 360
 * page's permission gating — financial figures are hidden from roles without
 * fee access. Navigation stays shallow: deep work happens in the existing
 * Profile / 360 pages.
 */

const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
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

const attendanceStatusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  present: 'success',
  absent: 'danger',
  late: 'warning',
  excused: 'info',
}

function InfoRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <span className="text-xs text-[var(--color-text-muted)]">{label}</span>
      <span className="truncate text-xs font-medium text-[var(--color-text-primary)]">
        {value ?? '—'}
      </span>
    </div>
  )
}

function SectionLabel({ children }: { children: string }) {
  return (
    <h3 className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)] mb-2">
      {children}
    </h3>
  )
}

export interface StudentInspectorProps {
  open: boolean
  studentId: string | null
  onClose: () => void
  /** Opens the existing edit modal in the list page. */
  onEdit: () => void
}

export function StudentInspector({ open, studentId, onClose, onEdit }: StudentInspectorProps) {
  const navigate = useNavigate()
  const { can } = usePermission()
  const showFinance = can(FEES_VIEW)

  const [data, setData] = useState<Student360Response | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  // One guarded loader for both the selection effect and the error retry — a
  // stale in-flight request (retry racing a selection change) never lands.
  const load = useCallback((id: string) => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    // Reset the previous student's data while the next loads — the skeleton
    // is honest rather than showing stale identity under fresh stats.
    setData(null)
    student360Api
      .get(Number(id))
      .then((res) => {
        if (fetchId === fetchIdRef.current) setData(res)
      })
      .catch((err: any) => {
        if (fetchId === fetchIdRef.current) {
          setError(err?.detail || 'Unable to load this student')
        }
      })
      .finally(() => {
        if (fetchId === fetchIdRef.current) setLoading(false)
      })
  }, [])

  useEffect(() => {
    if (!open || !studentId) return
    load(studentId)
  }, [open, studentId, load])

  const s = data?.identity

  return (
    <WorkspaceInspector
      open={open}
      onClose={onClose}
      title={s ? `${s.first_name} ${s.last_name}` : 'Student'}
      header={
        s && (
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[var(--color-brand-accent)] to-[var(--color-brand-accent-hover)] text-sm font-bold text-white shadow">
              {s.first_name[0]}
              {s.last_name[0]}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <p className="truncate text-sm font-semibold text-[var(--color-text-primary)]">
                  {s.first_name} {s.last_name}
                </p>
                <Badge variant={statusBadge[s.status]}>{s.status}</Badge>
              </div>
              <p className="mt-0.5 truncate text-xs text-[var(--color-text-tertiary)]">
                Student #{s.student_number}
                {s.email ? ` · ${s.email}` : ''}
              </p>
            </div>
          </div>
        )
      }
      loading={loading}
      error={error}
      onRetry={() => {
        if (studentId) load(studentId)
      }}
      emptyMessage="Select a student to preview their record."
      footer={
        s && (
          <>
            <Button variant="outline" size="sm" onClick={onEdit}>
              Edit
            </Button>
            <Button variant="outline" size="sm" onClick={() => navigate(`/students/${s.id}`)}>
              Profile
            </Button>
            <Button size="sm" onClick={() => navigate(`/students/${s.id}/360`)}>
              Open 360
            </Button>
          </>
        )
      }
    >
      {data && (
        <div className="space-y-5 p-4">
          {/* Quick stats */}
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2.5">
              <p className="text-base font-bold tabular-nums text-[var(--color-text-primary)]">
                {data.attendance.percentage}%
              </p>
              <p className="text-[11px] text-[var(--color-text-tertiary)]">Attendance</p>
            </div>
            {showFinance ? (
              <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2.5">
                <p
                  className={cn(
                    'text-base font-bold tabular-nums',
                    data.financial.total_outstanding > 0
                      ? 'text-[var(--color-danger)]'
                      : 'text-[var(--color-success-dark)]'
                  )}
                >
                  ${data.financial.total_outstanding.toLocaleString()}
                </p>
                <p className="text-[11px] text-[var(--color-text-tertiary)]">Outstanding</p>
              </div>
            ) : (
              <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2.5">
                <p className="text-base font-bold tabular-nums text-[var(--color-text-primary)]">
                  {data.attendance_records.length}
                </p>
                <p className="text-[11px] text-[var(--color-text-tertiary)]">Records</p>
              </div>
            )}
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2.5">
              <p className="truncate text-sm font-bold text-[var(--color-text-primary)]">
                {data.current_enrollment
                  ? [data.current_enrollment.class_name, data.current_enrollment.section_name]
                      .filter(Boolean)
                      .join('–')
                  : '—'}
              </p>
              <p className="text-[11px] text-[var(--color-text-tertiary)]">Class</p>
            </div>
          </div>

          {/* Enrollment */}
          {data.current_enrollment && (
            <div>
              <SectionLabel>Enrollment</SectionLabel>
              <div className="rounded-xl border border-[var(--color-border)] px-3 py-1">
                <InfoRow label="Academic year" value={data.current_enrollment.academic_year_name} />
                <InfoRow label="Enrolled" value={formatDate(data.current_enrollment.enrolled_at)} />
              </div>
            </div>
          )}

          {/* Personal */}
          <div>
            <SectionLabel>Personal</SectionLabel>
            <div className="rounded-xl border border-[var(--color-border)] px-3 py-1">
              <InfoRow label="Date of birth" value={formatDate(s?.date_of_birth)} />
              <InfoRow label="Guardians" value={data.guardians.length || undefined} />
              <InfoRow label="Emergency" value={data.health.emergency_contact} />
            </div>
          </div>

          {/* Recent attendance */}
          <div>
            <SectionLabel>Recent attendance</SectionLabel>
            {data.attendance_records.length === 0 ? (
              <p className="rounded-xl border border-dashed border-[var(--color-border)] px-3 py-4 text-center text-xs text-[var(--color-text-tertiary)]">
                No attendance recorded yet.
              </p>
            ) : (
              <div className="divide-y divide-[var(--color-border)] rounded-xl border border-[var(--color-border)] px-3">
                {data.attendance_records.slice(0, 3).map((r) => (
                  <div key={r.id} className="flex items-center justify-between py-2">
                    <span className="text-xs text-[var(--color-text-secondary)]">{r.attendance_date}</span>
                    <Badge variant={attendanceStatusBadge[r.status]}>{r.status}</Badge>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </WorkspaceInspector>
  )
}
