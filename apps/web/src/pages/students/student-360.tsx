import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { student360Api, type Student360Response } from '../../api/student-360/student-360-api'
import {
  Card, TabGroup, Badge, Button, Breadcrumbs, PageHeader, ErrorState,
} from '../../components/ui'
import { Timeline } from '../../components/timeline/timeline'
import { Can } from '../../components/auth/can'
import { usePermission } from '../../hooks/use-permission'
import { FEES_VIEW } from '../../types/permissions'
import { cn, formatDate } from '../../lib/utils'

const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  active: 'success',
  inactive: 'danger',
  graduated: 'info',
}

const attendanceStatusBadge: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  present: 'success',
  absent: 'danger',
  late: 'warning',
  excused: 'info',
}

const dueStatusBadge: Record<string, 'success' | 'warning' | 'danger'> = {
  paid: 'success',
  partially_paid: 'warning',
  unpaid: 'danger',
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

function InfoRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-[var(--color-border)] last:border-0">
      <span className="text-sm text-[var(--color-text-muted)]">{label}</span>
      <span className="text-sm font-medium text-[var(--color-text-primary)]">{value ?? '-'}</span>
    </div>
  )
}

// ── Tab: Overview ──────────────────────────────────────────────────────

function OverviewTab({ data }: { data: Student360Response }) {
  const { identity: s, current_enrollment: ce, financial: fin, attendance: att, guardians, contacts, health } = data
  return (
    <div className="space-y-6">
      {/* Hero Identity */}
      <Card className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-[var(--color-brand-accent)]/5 to-transparent pointer-events-none" />
        <div className="flex items-start gap-6 relative z-10">
          <div className="h-20 w-20 rounded-2xl bg-gradient-to-br from-[var(--color-brand-accent)] to-[var(--color-brand-accent-hover)] flex items-center justify-center text-white text-3xl font-bold shadow-lg shrink-0">
            {s.first_name[0]}{s.last_name[0]}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h2 className="text-2xl font-bold text-[var(--color-text-primary)]">{s.first_name} {s.last_name}</h2>
              <Badge variant={statusBadge[s.status]}>{s.status}</Badge>
            </div>
            <p className="text-sm text-[var(--color-text-tertiary)] mt-1">
              Student #{s.student_number} &middot; {s.email || 'No email'}
            </p>
            {ce && (
              <div className="mt-3 flex flex-wrap gap-4 text-sm">
                <span className="text-[var(--color-text-muted)]">
                  Current:{' '}
                  <span className="font-medium text-[var(--color-text-primary)]">
                    {[ce.class_name, ce.section_name].filter(Boolean).join(' - ')}
                  </span>
                </span>
                <span className="text-[var(--color-text-muted)]">
                  Year:{' '}
                  <span className="font-medium text-[var(--color-text-primary)]">{ce.academic_year_name}</span>
                </span>
              </div>
            )}
            <div className="flex gap-2 mt-4">
              <Button size="sm" onClick={() => window.open(`/students/${s.id}`, '_self')}>Full Profile</Button>
              <Button size="sm" variant="outline" onClick={() => window.open(`/fees/student-fees?studentId=${s.id}`, '_self')}>Manage Fees</Button>
            </div>
          </div>
        </div>
      </Card>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Attendance" value={`${att.percentage}%`} color={att.percentage >= 75 ? 'text-green-600' : 'text-red-600'} />
        <MetricCard label="Total Fees" value={`$${fin.total_fees_assigned.toLocaleString()}`} />
        <MetricCard label="Paid" value={`$${fin.total_paid.toLocaleString()}`} color="text-green-600" />
        <MetricCard label="Outstanding" value={`$${fin.total_outstanding.toLocaleString()}`} color={fin.total_outstanding > 0 ? 'text-red-600' : 'text-green-600'} />
      </div>

      {/* Details Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card title="Personal Details">
          <InfoRow label="Date of Birth" value={formatDate(s.date_of_birth)} />
          <InfoRow label="Status" value={s.status} />
          <InfoRow label="Email" value={s.email} />
          <InfoRow label="Student #" value={s.student_number} />
        </Card>

        <Card title="Guardians">
          {guardians.length === 0 ? (
            <p className="text-sm text-[var(--color-text-tertiary)]">No guardians recorded</p>
          ) : (
            <div className="space-y-3">
              {guardians.map((g, i) => (
                <div key={i} className="p-3 rounded-lg bg-[var(--color-surface-hover)]">
                  <p className="font-medium text-sm text-[var(--color-text-primary)]">{g.name}</p>
                  <p className="text-xs text-[var(--color-text-tertiary)]">{g.relationship} &middot; {g.contact}</p>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Health & Emergency">
          <InfoRow label="Blood Group" value={health.blood_group} />
          <InfoRow label="Allergies" value={health.allergies} />
          <InfoRow label="Medical Conditions" value={health.medical_conditions} />
          <InfoRow label="Emergency Contact" value={health.emergency_contact} />
        </Card>
      </div>

      {/* Transport & Hostel */}
      {(data.transport || data.hostel) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {data.transport && (
            <Card title="Transport">
              <InfoRow label="Route" value={data.transport.route} />
              <InfoRow label="Pickup" value={data.transport.pickup_point} />
              <InfoRow label="Drop-off" value={data.transport.dropoff_point} />
              <InfoRow label="Vehicle" value={data.transport.vehicle_number} />
            </Card>
          )}
          {data.hostel && (
            <Card title="Hostel">
              <InfoRow label="Hostel" value={data.hostel.hostel_name} />
              <InfoRow label="Room" value={data.hostel.room_number} />
              <InfoRow label="Bed" value={data.hostel.bed_number} />
            </Card>
          )}
        </div>
      )}
    </div>
  )
}

// ── Tab: Academic ──────────────────────────────────────────────────────

function AcademicTab({ data }: { data: Student360Response }) {
  return (
    <div className="space-y-6">
      {data.current_enrollment && (
        <Card title="Current Enrollment" variant="elevated">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-[var(--color-text-tertiary)]">Academic Year</p>
              <p className="font-semibold text-[var(--color-text-primary)]">{data.current_enrollment.academic_year_name || '-'}</p>
            </div>
            <div>
              <p className="text-xs text-[var(--color-text-tertiary)]">Class</p>
              <p className="font-semibold text-[var(--color-text-primary)]">{data.current_enrollment.class_name || '-'}</p>
            </div>
            <div>
              <p className="text-xs text-[var(--color-text-tertiary)]">Section</p>
              <p className="font-semibold text-[var(--color-text-primary)]">{data.current_enrollment.section_name || '-'}</p>
            </div>
            <div>
              <p className="text-xs text-[var(--color-text-tertiary)]">Enrolled</p>
              <p className="font-semibold text-[var(--color-text-primary)]">{formatDate(data.current_enrollment.enrolled_at)}</p>
            </div>
          </div>
        </Card>
      )}

      <Card title="Enrollment History">
        {data.academic_history.length === 0 ? (
          <p className="text-sm text-[var(--color-text-tertiary)] py-4 text-center">No enrollment history</p>
        ) : (
          <div className="space-y-0 divide-y divide-[var(--color-border)]">
            {data.academic_history.map((rec) => (
              <div key={rec.enrollment_id} className="flex items-center justify-between py-3">
                <div>
                  <p className="font-medium text-[var(--color-text-primary)] text-sm">
                    {rec.class_name || 'N/A'} {rec.section_name ? `- ${rec.section_name}` : ''}
                  </p>
                  <p className="text-xs text-[var(--color-text-tertiary)]">
                    {rec.academic_year_name || 'N/A'} &middot; Enrolled {formatDate(rec.enrolled_at)}
                  </p>
                </div>
                <Badge variant={rec.status === 'active' ? 'success' : 'info'}>{rec.status}</Badge>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

// ── Tab: Attendance ────────────────────────────────────────────────────

function AttendanceTab({ data }: { data: Student360Response }) {
  const { attendance: att, attendance_records: records } = data
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <MetricCard label="Total" value={att.total} />
        <MetricCard label="Present" value={att.present} color="text-green-600" />
        <MetricCard label="Absent" value={att.absent} color="text-red-600" />
        <MetricCard label="Late" value={att.late} color="text-yellow-600" />
        <MetricCard label="Excused" value={att.excused} color="text-blue-600" />
      </div>

      <Card title="Attendance Rate" subtitle="Last 90 days">
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
            <p>{att.present} days present out of {att.total} total days</p>
            <p className="mt-1">{att.absent + att.late} days absent or late</p>
          </div>
        </div>
      </Card>

      <Card title="Recent Records">
        {records.length === 0 ? (
          <p className="text-sm text-[var(--color-text-tertiary)] py-4 text-center">No recent records</p>
        ) : (
          <div className="space-y-0 divide-y divide-[var(--color-border)]">
            {records.map((r) => (
              <div key={r.id} className="flex items-center justify-between py-2.5">
                <span className="text-sm text-[var(--color-text-primary)]">{r.attendance_date}</span>
                <Badge variant={attendanceStatusBadge[r.status]}>{r.status}</Badge>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

// ── Tab: Finance ───────────────────────────────────────────────────────

function FinanceTab({ data }: { data: Student360Response }) {
  const { financial: fin, fee_dues: dues, payments } = data
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard label="Total Fees" value={`$${fin.total_fees_assigned.toLocaleString()}`} />
        <MetricCard label="Paid" value={`$${fin.total_paid.toLocaleString()}`} color="text-green-600" />
        <MetricCard label="Outstanding" value={`$${fin.total_outstanding.toLocaleString()}`}
          color={fin.total_outstanding > 0 ? 'text-red-600' : 'text-green-600'} />
        <MetricCard label="Dues Remaining" value={fin.unpaid_count + fin.partially_paid_count}
          color={(fin.unpaid_count + fin.partially_paid_count) > 0 ? 'text-yellow-600' : 'text-green-600'} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="Fee Dues">
          {dues.length === 0 ? (
            <p className="text-sm text-[var(--color-text-tertiary)] py-4 text-center">No fee dues</p>
          ) : (
            <div className="space-y-0 divide-y divide-[var(--color-border)]">
              {dues.map((d) => (
                <div key={d.id} className="py-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-sm text-[var(--color-text-primary)]">{d.fee_type_name || 'Fee'}</span>
                    <Badge variant={dueStatusBadge[d.status]}>{d.status.replace('_', ' ')}</Badge>
                  </div>
                  <div className="flex gap-4 text-xs text-[var(--color-text-tertiary)]">
                    <span>Total: ${d.original_amount.toLocaleString()}</span>
                    <span>Paid: ${d.amount_paid.toLocaleString()}</span>
                    <span className={d.balance > 0 ? 'text-red-600 font-medium' : 'text-green-600'}>
                      Balance: ${d.balance.toLocaleString()}
                    </span>
                  </div>
                  {d.due_date && <p className="text-xs text-[var(--color-text-tertiary)] mt-1">Due: {d.due_date}</p>}
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Recent Payments">
          {payments.length === 0 ? (
            <p className="text-sm text-[var(--color-text-tertiary)] py-4 text-center">No payments recorded</p>
          ) : (
            <div className="space-y-0 divide-y divide-[var(--color-border)]">
              {payments.slice(0, 15).map((p) => (
                <div key={p.id} className="flex items-center justify-between py-2.5">
                  <div>
                    <p className="text-sm font-medium text-[var(--color-text-primary)]">${p.amount.toLocaleString()}</p>
                    <p className="text-xs text-[var(--color-text-tertiary)]">{p.payment_date || p.created_at}</p>
                  </div>
                  <div className="text-right text-xs text-[var(--color-text-tertiary)]">
                    <p>{p.payment_method || '-'}</p>
                    {p.receipt_number && <p>Receipt: {p.receipt_number}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

// ── Tab: Documents ─────────────────────────────────────────────────────

function DocumentsTab({ data }: { data: Student360Response }) {
  return (
    <div className="space-y-6">
      <Card title="Student Documents">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            { name: 'Admission Form', type: 'form', icon: '📋' },
            { name: 'ID Card', type: 'id', icon: '🪪' },
            { name: 'Transcript', type: 'academic', icon: '📜' },
            { name: 'Fee Receipts', type: 'finance', icon: '🧾' },
            { name: 'Medical Records', type: 'health', icon: '🏥' },
            { name: 'Transfer Certificate', type: 'tc', icon: '📄' },
          ].map((doc) => (
            <Card key={doc.name} variant="bordered" className="hover:shadow-sm cursor-pointer transition-shadow">
              <div className="flex items-center gap-3">
                <span className="text-2xl">{doc.icon}</span>
                <div>
                  <p className="font-medium text-sm text-[var(--color-text-primary)]">{doc.name}</p>
                  <p className="text-xs text-[var(--color-text-tertiary)] capitalize">{doc.type} document</p>
                </div>
              </div>
            </Card>
          ))}
        </div>
        <p className="text-xs text-[var(--color-text-tertiary)] mt-4 text-center">
          Document management coming soon &mdash; upload and manage files here.
        </p>
      </Card>

      <Card title="Health Information">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <InfoRow label="Blood Group" value={data.health.blood_group} />
          <InfoRow label="Allergies" value={data.health.allergies} />
          <InfoRow label="Medical Conditions" value={data.health.medical_conditions} />
          <InfoRow label="Emergency Contact" value={data.health.emergency_contact} />
        </div>
      </Card>
    </div>
  )
}

// ── Tab: Communication ─────────────────────────────────────────────────

function CommunicationTab({ data }: { data: Student360Response }) {
  const { communications, guardians } = data
  return (
    <div className="space-y-6">
      <Card title="Contact Information">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Student Contacts</h4>
            {data.contacts.length === 0 ? (
              <p className="text-sm text-[var(--color-text-tertiary)]">No contacts recorded</p>
            ) : (
              <div className="space-y-2">
                {data.contacts.map((c, i) => (
                  <div key={i} className="flex items-center justify-between p-2 rounded bg-[var(--color-surface-hover)]">
                    <span className="text-sm capitalize text-[var(--color-text-muted)]">{c.type}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-[var(--color-text-primary)]">{c.value}</span>
                      {c.is_primary && <Badge variant="info">Primary</Badge>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div>
            <h4 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">Guardians</h4>
            {guardians.length === 0 ? (
              <p className="text-sm text-[var(--color-text-tertiary)]">No guardians recorded</p>
            ) : (
              <div className="space-y-2">
                {guardians.map((g, i) => (
                  <div key={i} className="p-2 rounded bg-[var(--color-surface-hover)]">
                    <p className="text-sm font-medium text-[var(--color-text-primary)]">{g.name}</p>
                    <p className="text-xs text-[var(--color-text-tertiary)]">{g.relationship} &middot; {g.contact}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </Card>

      <Card title="Recent Communications">
        {communications.length === 0 ? (
          <div className="py-8 text-center">
            <div className="flex items-center justify-center h-12 w-12 rounded-full bg-[var(--color-surface-hover)] mx-auto mb-3">
              <svg className="h-6 w-6 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <p className="text-sm text-[var(--color-text-tertiary)]">No communications recorded</p>
            <p className="text-xs text-[var(--color-text-tertiary)] mt-1">Communication history will appear here once messages are sent.</p>
          </div>
        ) : (
          <div className="space-y-0 divide-y divide-[var(--color-border)]">
            {communications.map((c, i) => (
              <div key={i} className="py-3 flex items-start gap-3">
                <div className="h-8 w-8 rounded-full bg-[var(--color-surface-hover)] flex items-center justify-center shrink-0 mt-0.5">
                  <span className="text-xs font-medium text-[var(--color-text-muted)]">{(c as any).type?.[0] || 'N'}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-[var(--color-text-primary)]">{(c as any).subject || 'Message'}</p>
                  <p className="text-xs text-[var(--color-text-tertiary)] truncate">{(c as any).body || ''}</p>
                  <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">{(c as any).created_at || ''}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

// ── Tab: Risk ─────────────────────────────────────────────────────────

const riskSeverityBadge: Record<string, 'danger' | 'warning' | 'info' | 'success'> = {
  critical: 'danger',
  high: 'danger',
  medium: 'warning',
  low: 'info',
}

const riskSeverityDot: Record<string, string> = {
  critical: 'bg-[var(--color-danger)]',
  high: 'bg-[var(--color-danger)]',
  medium: 'bg-[var(--color-warning)]',
  low: 'bg-[var(--color-info)]',
}

const riskCategoryLabel: Record<string, string> = {
  attendance: 'Attendance',
  finance: 'Finance',
  academic: 'Academic',
  documents: 'Documents',
  admissions: 'Admissions',
  operational: 'Operational',
}

function RiskTab({ data }: { data: Student360Response }) {
  const { can } = usePermission()
  // Never expose finance findings to roles without finance access.
  const findings = (data.risk_findings || []).filter(
    (f) => f.category !== 'finance' || can(FEES_VIEW)
  )
  return (
    <div className="space-y-6">
      <div className="flex items-start gap-3 rounded-2xl border border-[var(--color-info)]/20 bg-[var(--color-info)]/5 p-4">
        <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-info)]/10 flex-shrink-0">
          <svg className="h-4.5 w-4.5 text-[var(--color-info)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <div>
          <p className="text-sm font-semibold text-[var(--color-text-primary)]">Risk &amp; Attention</p>
          <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">
            Deterministic findings from the school's rule engine. Each finding includes a reason, a recommended action, and a score.
          </p>
        </div>
      </div>

      {findings.length === 0 ? (
        <div className="rounded-2xl border border-[var(--color-success)]/20 bg-[var(--color-success)]/5 p-8 text-center">
          <p className="text-sm font-semibold text-[var(--color-success-dark)]">No active risk findings</p>
          <p className="text-xs text-[var(--color-success)]/70 mt-1">This student has no open findings from the risk engine.</p>
        </div>
      ) : (
        <div className="space-y-2.5">
          {findings.map((f) => (
            <div key={f.id} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 animate-fade-in-up" style={{ animationFillMode: 'both' }}>
              <div className="flex items-start gap-3">
                <span className={cn('mt-1.5 inline-block h-2 w-2 rounded-full flex-shrink-0', riskSeverityDot[f.severity])} aria-hidden="true" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant={riskSeverityBadge[f.severity]}>{f.severity}</Badge>
                    <Badge variant="neutral">{riskCategoryLabel[f.category] || f.category}</Badge>
                    <span className="text-[11px] text-[var(--color-text-muted)] tabular-nums">Score {Math.round(f.score)}</span>
                  </div>
                  <p className="text-sm text-[var(--color-text-primary)] mt-2">{f.reason}</p>
                  <p className="text-xs text-[var(--color-text-secondary)] mt-1.5">
                    <span className="font-medium">Recommended:</span> {f.recommended_action}
                  </p>
                  <p className="text-[11px] text-[var(--color-text-muted)] mt-1.5">Detected {formatDate(f.detected_at)}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Tab: Timeline (unified operational timeline) ──────────────────────

function TimelineTab({ data }: { data: Student360Response }) {
  return (
    <div className="space-y-3">
      <div className="flex items-start gap-3 rounded-2xl border border-[var(--color-info)]/20 bg-[var(--color-info)]/5 p-4">
        <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-info)]/10 flex-shrink-0">
          <svg className="h-4.5 w-4.5 text-[var(--color-info)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <div>
          <p className="text-sm font-semibold text-[var(--color-text-primary)]">Activity Timeline</p>
          <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">
            Unified activity — audit, payments, enrollments &amp; risk findings for this student.
          </p>
        </div>
      </div>
      <Timeline params={{ entity_type: 'student', entity_id: data.identity.id }} compact />
    </div>
  )
}

// ── Main 360 Page ──────────────────────────────────────────────────────

const ALL_TABS = [
  { id: 'overview', label: 'Overview', permission: null },
  { id: 'academic', label: 'Academic', permission: null },
  { id: 'attendance', label: 'Attendance', permission: null },
  { id: 'finance', label: 'Finance', permission: FEES_VIEW },
  { id: 'documents', label: 'Documents', permission: null },
  { id: 'risk', label: 'Risk', permission: null },
  { id: 'communication', label: 'Communication', permission: null },
  { id: 'timeline', label: 'Timeline', permission: null },
]

export function Student360Page() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('overview')
  const [data, setData] = useState<Student360Response | null>(null)
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
    student360Api.get(Number(id))
      .then(setData)
      .catch((err) => setError(err?.detail || 'Failed to load student 360 view'))
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
    return <ErrorState message="Student not found" />
  }

  const s = data.identity

  return (
    <div className="space-y-6 animate-fade-in-up">
      <Breadcrumbs items={[
        { label: 'Students', href: '/students' },
        { label: `${s.first_name} ${s.last_name}`, href: `/students/${s.id}` },
        { label: '360 View' },
      ]} />

      <div className="flex items-center justify-between gap-4">
        <PageHeader
          title={`${s.first_name} ${s.last_name}`}
          subtitle={`Student #${s.student_number} - 360° Overview`}
          actions={<Badge variant={statusBadge[s.status]}>{s.status}</Badge>}
        />
        <div className="flex gap-2 shrink-0">
          <Button variant="outline" size="sm" onClick={() => navigate(`/students/${s.id}`)}>
            Standard View
          </Button>
          <Button variant="outline" size="sm" onClick={() => navigate('/students')}>
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
        {activeTab === 'academic' && <AcademicTab data={data} />}
        {activeTab === 'attendance' && <AttendanceTab data={data} />}
        {activeTab === 'finance' && (
          <Can permission={FEES_VIEW} fallback={
            <Card><div className="py-8 text-center text-sm text-[var(--color-text-tertiary)]">You do not have permission to view financial data.</div></Card>
          }>
            <FinanceTab data={data} />
          </Can>
        )}
        {activeTab === 'documents' && <DocumentsTab data={data} />}
        {activeTab === 'risk' && <RiskTab data={data} />}
        {activeTab === 'communication' && <CommunicationTab data={data} />}
        {activeTab === 'timeline' && <TimelineTab data={data} />}
      </div>
    </div>
  )
}
