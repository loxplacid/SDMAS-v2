import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { admissionApi, ADMISSION_STATUSES, type ApplicationListParams, type AdmissionApplicationResponse } from '../../api/admission/admission-api'
import { Card, Table, Pagination, Input, Select, Button, ErrorState, StatusBadge, SearchInput, EmptyState, getEmptyState, useToast } from '../../components/ui'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { capitalize, debounce } from '../../lib/utils'

const statusVariantMap: Record<string, string> = {
  inquiry: 'neutral',
  application_submitted: 'info',
  documents_uploaded: 'info',
  verified: 'success',
  interview_scheduled: 'warning',
  interview_completed: 'warning',
  merit_listed: 'success',
  seat_allocated: 'success',
  fee_paid: 'success',
  enrolled: 'success',
  student_created: 'success',
  rejected: 'danger',
}

function getStatusVariant(status: string): 'success' | 'warning' | 'danger' | 'info' | 'neutral' {
  return (statusVariantMap[status] as 'success' | 'warning' | 'danger' | 'info' | 'neutral') || 'neutral'
}

export function ApplicationListPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const searchRef = useRef<HTMLInputElement>(null)

  useKeyboardShortcut({
    '/': (e) => { e.preventDefault(); searchRef.current?.focus() },
    'n': () => navigate('/admissions/new'),
  }, [])

  const [data, setData] = useState<AdmissionApplicationResponse[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchIdRef = useRef(0)

  const fetchApplications = useCallback(async (params: ApplicationListParams) => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    try {
      const result = await admissionApi.listApplications(params)
      if (fetchId === fetchIdRef.current) {
        setData(result.items)
        setTotal(result.total)
        setPages(result.pages)
        setPage(result.page)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load applications')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchApplications({ page, size, search: search || undefined, status: statusFilter || undefined })
  }, [page, size, statusFilter, fetchApplications])

  const debouncedSearch = useCallback(
    debounce((value: string) => { setSearch(value); setPage(1) }, 300), []
  )

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    debouncedSearch(e.target.value)
  }

  const emptyState = getEmptyState('admissions')

  return (
    <div className="space-y-8 animate-fade-in-up">
      {/* Narrative header */}
      <div>
        <p className="text-sm font-medium text-[var(--color-brand-accent)] tracking-wide mb-1">Admissions</p>
        <h1 className="text-3xl lg:text-4xl font-extrabold text-[var(--color-text-primary)] tracking-tight leading-tight">
          Applications
        </h1>
        <p className="text-base text-[var(--color-text-tertiary)] mt-2 max-w-xl">
          {total > 0
            ? `${total} application${total !== 1 ? 's' : ''} in the admissions pipeline. Review, verify, and process applicants.`
            : 'Track your admissions pipeline. Applications move through verification, interview, merit listing, and enrollment.'}
        </p>
      </div>

      {/* Search & filters bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3 flex-1 max-w-lg">
          <div className="flex-1 min-w-[200px]">
            <SearchInput
              ref={searchRef}
              placeholder="Search by name, email, or phone..."
              onChange={handleSearchChange}
              showKbdHint
            />
          </div>
          <Select
            options={[
              { value: '', label: 'All statuses' },
              ...ADMISSION_STATUSES.map((s) => ({ value: s, label: capitalize(s.replace(/_/g, ' ')) })),
            ]}
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
          />
        </div>
        <Button onClick={() => navigate('/admissions/new')} className="relative">
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Inquiry
          <kbd className="ml-2 hidden sm:inline-flex items-center px-1.5 py-0.5 rounded bg-white/20 text-[10px] font-medium text-white/80">N</kbd>
        </Button>
      </div>

      {/* Data table area */}
      <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] overflow-hidden">
        {loading ? (
          <Table columns={[]} data={[]} loading={true} keyExtractor={() => ''} emptyMessage="" />
        ) : error ? (
          <ErrorState message={error} onRetry={() => fetchApplications({ page, size, search: search || undefined, status: statusFilter || undefined })} />
        ) : data.length === 0 ? (
          <div className="p-8">
            <EmptyState
              title={emptyState.title}
              description={emptyState.description}
              action={{ label: 'New Inquiry', onClick: () => navigate('/admissions/new') }}
            />
          </div>
        ) : (
          <>
            <Table
              columns={[
                { key: 'applicant_name', header: 'Applicant', render: (a: AdmissionApplicationResponse) => (
                  <span className="font-medium text-[var(--color-text-primary)]">{a.applicant_name}</span>
                )},
                { key: 'email', header: 'Email', render: (a: AdmissionApplicationResponse) => a.email || '-' },
                { key: 'phone', header: 'Phone', render: (a: AdmissionApplicationResponse) => a.phone || '-' },
                { key: 'status', header: 'Status', render: (a: AdmissionApplicationResponse) => (
                  <StatusBadge status={a.status} variant={getStatusVariant(a.status)} />
                )},
                { key: 'created_at', header: 'Created', render: (a: AdmissionApplicationResponse) => new Date(a.created_at).toLocaleDateString() },
              ]}
              data={data}
              keyExtractor={(a) => a.id}
              emptyMessage="No applications found"
              onRowClick={(a) => navigate(`/admissions/${a.id}`)}
            />
            <Pagination
              page={page}
              size={size}
              total={total}
              pages={pages}
              onPageChange={setPage}
              onSizeChange={(s) => { setSize(s); setPage(1) }}
            />
          </>
        )}
      </div>
    </div>
  )
}

export default ApplicationListPage
