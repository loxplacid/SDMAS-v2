import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { admissionApi, ADMISSION_STATUSES, type AdmissionApplicationResponse, type AdmissionDocumentResponse, type AdmissionInterviewResponse, type AdmissionSeatAllocationResponse, type AdmissionStatus } from '../../api/admission/admission-api'
import { Card, Button, ErrorState, BreadcrumbBar, PageHeader, StatusBadge, Badge, Modal, Input, Select, Alert, useToast, Loading } from '../../components/ui'
import { capitalize, formatDateTime } from '../../lib/utils'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const statusMeta: Record<string, { variant: 'success' | 'warning' | 'danger' | 'info' | 'neutral'; label: string }> = {
  inquiry: { variant: 'neutral', label: 'Inquiry' },
  application_submitted: { variant: 'info', label: 'Application Submitted' },
  documents_uploaded: { variant: 'info', label: 'Documents Uploaded' },
  verified: { variant: 'success', label: 'Verified' },
  interview_scheduled: { variant: 'warning', label: 'Interview Scheduled' },
  interview_completed: { variant: 'warning', label: 'Interview Completed' },
  merit_listed: { variant: 'success', label: 'Merit Listed' },
  seat_allocated: { variant: 'success', label: 'Seat Allocated' },
  fee_paid: { variant: 'success', label: 'Fee Paid' },
  enrolled: { variant: 'success', label: 'Enrolled' },
  student_created: { variant: 'success', label: 'Student Created' },
  rejected: { variant: 'danger', label: 'Rejected' },
}

function getNextStatus(current: string): AdmissionStatus | null {
  const idx = ADMISSION_STATUSES.indexOf(current as AdmissionStatus)
  if (idx < 0 || idx >= ADMISSION_STATUSES.length - 1) return null
  return ADMISSION_STATUSES[idx + 1]
}

function getDocVerificationVariant(status: string): 'success' | 'warning' | 'danger' | 'info' | 'neutral' {
  if (status === 'verified') return 'success'
  if (status === 'rejected') return 'danger'
  return 'warning'
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { showToast } = useToast()

  const [application, setApplication] = useState<AdmissionApplicationResponse | null>(null)
  const [documents, setDocuments] = useState<AdmissionDocumentResponse[]>([])
  const [interviews, setInterviews] = useState<AdmissionInterviewResponse[]>([])
  const [allocations, setAllocations] = useState<AdmissionSeatAllocationResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Modal states
  const [transitionModal, setTransitionModal] = useState(false)
  const [transitionStatus, setTransitionStatus] = useState<string>('')
  const [transitionRemarks, setTransitionRemarks] = useState('')
  const [transitioning, setTransitioning] = useState(false)

  const [docModal, setDocModal] = useState(false)
  const [docType, setDocType] = useState('')
  const [docFileName, setDocFileName] = useState('')
  const [uploadingDoc, setUploadingDoc] = useState(false)

  const [interviewModal, setInterviewModal] = useState(false)
  const [interviewDate, setInterviewDate] = useState('')
  const [interviewMode, setInterviewMode] = useState('in-person')
  const [scheduling, setScheduling] = useState(false)

  const loadData = async () => {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const [app, docs, interviewsData, allocs] = await Promise.all([
        admissionApi.getApplication(Number(id)),
        admissionApi.getApplicationDocuments(Number(id)),
        admissionApi.getApplicationInterviews(Number(id)),
        admissionApi.getApplicationAllocations(Number(id)),
      ])
      setApplication(app)
      setDocuments(docs)
      setInterviews(interviewsData)
      setAllocations(allocs)
    } catch (err: any) {
      setError(err?.detail || 'Failed to load application')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [id])

  // Status transition
  const handleTransition = async () => {
    if (!application || !transitionStatus) return
    setTransitioning(true)
    try {
      const updated = await admissionApi.transitionStatus(application.id, {
        new_status: transitionStatus,
        remarks: transitionRemarks || null,
      })
      setApplication(updated)
      setTransitionModal(false)
      setTransitionRemarks('')
      showToast(`Status updated to "${statusMeta[transitionStatus]?.label || transitionStatus}"`, 'success')
    } catch (err: any) {
      showToast(err?.detail || 'Failed to update status', 'error')
    } finally {
      setTransitioning(false)
    }
  }

  const handleAdvance = async () => {
    if (!application) return
    const next = getNextStatus(application.status)
    if (!next) return
    setTransitionStatus(next)
    setTransitionModal(true)
  }

  // Document upload
  const handleUploadDoc = async () => {
    if (!application || !docType || !docFileName) return
    setUploadingDoc(true)
    try {
      const doc = await admissionApi.uploadDocument(application.id, {
        document_type: docType,
        file_name: docFileName,
      })
      setDocuments((prev) => [...prev, doc])
      setDocModal(false)
      setDocType('')
      setDocFileName('')
      showToast('Document uploaded', 'success')
    } catch (err: any) {
      showToast(err?.detail || 'Failed to upload document', 'error')
    } finally {
      setUploadingDoc(false)
    }
  }

  const handleVerifyDoc = async (docId: number, status: string) => {
    try {
      const updated = await admissionApi.verifyDocument(docId, status)
      setDocuments((prev) => prev.map((d) => (d.id === updated.id ? updated : d)))
      showToast(`Document ${status}`, 'success')
    } catch (err: any) {
      showToast(err?.detail || 'Failed to verify document', 'error')
    }
  }

  // Schedule interview
  const handleScheduleInterview = async () => {
    if (!application) return
    setScheduling(true)
    try {
      const interview = await admissionApi.scheduleInterview(application.id, {
        scheduled_date: interviewDate || null,
        interview_mode: interviewMode,
      })
      setInterviews((prev) => [...prev, interview])
      setInterviewModal(false)
      setInterviewDate('')
      showToast('Interview scheduled', 'success')
    } catch (err: any) {
      showToast(err?.detail || 'Failed to schedule interview', 'error')
    } finally {
      setScheduling(false)
    }
  }

  if (loading) return (
    <Loading />
  )
  if (error) return <ErrorState message={error} onRetry={loadData} />
  if (!application) return <ErrorState message="Application not found" />

  const meta = statusMeta[application.status]
  const currentIdx = ADMISSION_STATUSES.indexOf(application.status as AdmissionStatus)

  return (
    <div className="space-y-6 animate-fade-in-up">
      <BreadcrumbBar
        items={[
          { label: 'Admissions', href: '/admissions' },
          { label: 'Applications', href: '/admissions/applications' },
          { label: application.applicant_name },
        ]}
      />

      <PageHeader
        title={application.applicant_name}
        subtitle={application.email || application.phone || 'No contact info'}
        actions={
          <div className="flex items-center gap-2">
            <StatusBadge status={application.status} variant={meta?.variant} />
            {application.status !== 'rejected' && application.status !== 'student_created' && (
              <Button size="sm" onClick={handleAdvance}>
                Advance to {getNextStatus(application.status) ? capitalize(getNextStatus(application.status)!.replace(/_/g, ' ')) : 'Next'}
              </Button>
            )}
          </div>
        }
      />

      {/* Workflow Timeline */}
      <Card className="overflow-hidden">
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Workflow Progress</h3>
        <div className="flex flex-wrap items-center gap-1.5">
          {ADMISSION_STATUSES.filter((s) => s !== 'rejected').map((status, i) => {
            const stepMeta = statusMeta[status]
            const isPast = i < currentIdx
            const isCurrent = i === currentIdx
            const isFuture = i > currentIdx

            return (
              <div key={status} className="flex items-center gap-1.5">
                <span
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-all ${
                    isCurrent
                      ? 'bg-[var(--color-brand-accent)] text-white shadow-sm scale-105'
                      : isPast
                        ? 'bg-[var(--color-success-light)] text-[var(--color-success-dark)]'
                        : 'bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]'
                  }`}
                >
                  {isPast && (
                    <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                  {stepMeta.label}
                </span>
                {i < ADMISSION_STATUSES.length - 2 && (
                  <svg className={`h-3.5 w-3.5 flex-shrink-0 ${isFuture ? 'text-[var(--color-text-muted)]' : 'text-[var(--color-text-tertiary)]'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                )}
              </div>
            )
          })}
        </div>
        {application.status === 'rejected' && (
          <div className="mt-3">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-[var(--color-danger-light)] text-[var(--color-danger-dark)]">
              <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              Rejected
            </span>
          </div>
        )}
      </Card>

      {/* Info Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="Personal Information" className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)]">
          <dl className="space-y-3 text-sm">
            {[
              ['Name', application.applicant_name],
              ['Email', application.email || '-'],
              ['Phone', application.phone || '-'],
              ['Date of Birth', application.date_of_birth ? new Date(application.date_of_birth).toLocaleDateString() : '-'],
              ['Address', application.address || '-'],
              ['Source', application.source ? capitalize(application.source) : '-'],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between items-center">
                <dt className="text-[var(--color-text-muted)]">{label}</dt>
                <dd className="font-medium text-[var(--color-text-primary)] text-right">{value}</dd>
              </div>
            ))}
          </dl>
        </Card>

        <Card title="Application Details" className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)]">
          <dl className="space-y-3 text-sm">
            {[
              ['Previous Education', application.previous_education || '-'],
              ['Entrance Score', application.entrance_score?.toString() || '-'],
              ['Status', application.status.replace(/_/g, ' ')],
              ['Applied At', formatDateTime(application.applied_at)],
              ['Enrolled At', formatDateTime(application.enrolled_at)],
              ['Created', formatDateTime(application.created_at)],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between items-center">
                <dt className="text-[var(--color-text-muted)]">{label}</dt>
                <dd className="font-medium text-[var(--color-text-primary)] text-right">{value}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </div>

      {/* Remarks */}
      {application.remarks && (
        <Card title="Remarks">
          <p className="text-sm text-[var(--color-text-secondary)]">{application.remarks}</p>
        </Card>
      )}

      {/* Documents */}
      <Card
        title="Documents"
        actions={
          <Button size="sm" onClick={() => setDocModal(true)}>
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Upload
          </Button>
        }
      >
        {documents.length === 0 ? (
          <p className="text-sm text-[var(--color-text-muted)]">No documents uploaded yet.</p>
        ) : (
          <div className="divide-y divide-[var(--color-border)]">
            {documents.map((doc) => (
              <div key={doc.id} className="flex items-center justify-between py-3 first:pt-0 last:pb-0">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-[var(--color-text-primary)]">{doc.document_type}</p>
                  <p className="text-xs text-[var(--color-text-muted)]">{doc.file_name}</p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <Badge variant={getDocVerificationVariant(doc.verification_status)} dot>
                    {capitalize(doc.verification_status)}
                  </Badge>
                  {doc.verification_status === 'pending' && (
                    <div className="flex gap-1">
                      <Button size="xs" variant="success" onClick={() => handleVerifyDoc(doc.id, 'verified')}>Verify</Button>
                      <Button size="xs" variant="danger" onClick={() => handleVerifyDoc(doc.id, 'rejected')}>Reject</Button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Interviews */}
      <Card
        title="Interviews"
        actions={
          <Button size="sm" onClick={() => setInterviewModal(true)}>
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Schedule
          </Button>
        }
      >
        {interviews.length === 0 ? (
          <p className="text-sm text-[var(--color-text-muted)]">No interviews scheduled yet.</p>
        ) : (
          <div className="divide-y divide-[var(--color-border)]">
            {interviews.map((iv) => (
              <div key={iv.id} className="flex items-center justify-between py-3 first:pt-0 last:pb-0">
                <div>
                  <p className="text-sm font-medium text-[var(--color-text-primary)]">
                    {iv.scheduled_date ? new Date(iv.scheduled_date).toLocaleDateString() : 'Date TBD'} — {capitalize(iv.interview_mode || 'TBD')}
                  </p>
                  {iv.panel_members && <p className="text-xs text-[var(--color-text-muted)]">Panel: {iv.panel_members}</p>}
                  {iv.score !== null && <p className="text-xs text-[var(--color-brand-accent)]">Score: {iv.score}</p>}
                </div>
                <StatusBadge status={iv.status} />
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Seat Allocations */}
      {allocations.length > 0 && (
        <Card title="Seat Allocations">
          <div className="divide-y divide-[var(--color-border)]">
            {allocations.map((a) => (
              <div key={a.id} className="flex items-center justify-between py-3 first:pt-0 last:pb-0">
                <div>
                  <p className="text-sm font-medium text-[var(--color-text-primary)]">Program #{a.program_id}</p>
                  <p className="text-xs text-[var(--color-text-muted)]">Fee: ${(a.fee_amount / 100).toFixed(2)}</p>
                </div>
                <StatusBadge status={a.status} />
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        <Button variant="outline" onClick={() => navigate('/admissions/applications')}>Back to List</Button>
        {application.status !== 'rejected' && application.status !== 'student_created' && (
          <Button variant="danger" onClick={() => {
            setTransitionStatus('rejected')
            setTransitionModal(true)
          }}>
            Reject Application
          </Button>
        )}
      </div>

      {/* ── Transition Modal ── */}
      <Modal
        open={transitionModal}
        onClose={() => setTransitionModal(false)}
        title={`Transition to "${capitalize((transitionStatus || '').replace(/_/g, ' '))}"`}
        footer={
          <>
            <Button variant="outline" onClick={() => setTransitionModal(false)}>Cancel</Button>
            <Button
              onClick={handleTransition}
              loading={transitioning}
              variant={transitionStatus === 'rejected' ? 'danger' : 'primary'}
            >
              {transitionStatus === 'rejected' ? 'Reject' : 'Update Status'}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {transitionStatus === 'rejected' ? (
            <Alert variant="warning">This will reject the application. This action can be noted with a remark.</Alert>
          ) : (
            <p className="text-sm text-[var(--color-text-secondary)]">
              Advance from <strong>{capitalize(application.status.replace(/_/g, ' '))}</strong> to{' '}
              <strong>{capitalize((transitionStatus || '').replace(/_/g, ' '))}</strong>?
            </p>
          )}
          <Input
            label="Remarks (optional)"
            value={transitionRemarks}
            onChange={(e) => setTransitionRemarks(e.target.value)}
            placeholder="Optional note about this transition"
          />
        </div>
      </Modal>

      {/* ── Document Upload Modal ── */}
      <Modal
        open={docModal}
        onClose={() => setDocModal(false)}
        title="Upload Document"
        footer={
          <>
            <Button variant="outline" onClick={() => setDocModal(false)}>Cancel</Button>
            <Button onClick={handleUploadDoc} loading={uploadingDoc}>Upload</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input
            label="Document Type"
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
            placeholder="e.g. Transcript, ID Proof, Photo"
            required
          />
          <Input
            label="File Name"
            value={docFileName}
            onChange={(e) => setDocFileName(e.target.value)}
            placeholder="e.g. transcript.pdf"
            required
          />
        </div>
      </Modal>

      {/* ── Schedule Interview Modal ── */}
      <Modal
        open={interviewModal}
        onClose={() => setInterviewModal(false)}
        title="Schedule Interview"
        footer={
          <>
            <Button variant="outline" onClick={() => setInterviewModal(false)}>Cancel</Button>
            <Button onClick={handleScheduleInterview} loading={scheduling}>Schedule</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input
            label="Scheduled Date"
            type="date"
            value={interviewDate}
            onChange={(e) => setInterviewDate(e.target.value)}
          />
          <Select
            label="Interview Mode"
            value={interviewMode}
            onChange={(e) => setInterviewMode(e.target.value)}
            options={[
              { value: 'in-person', label: 'In Person' },
              { value: 'online', label: 'Online' },
            ]}
          />
        </div>
      </Modal>
    </div>
  )
}

export default ApplicationDetailPage
