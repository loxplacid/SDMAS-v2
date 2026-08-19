import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { admissionApi, type AdmissionMeritEntryResponse } from '../../api/admission/admission-api'
import { Card, Table, Pagination, Input, Select, Button, ErrorState, StatusBadge, EmptyState, useToast } from '../../components/ui'
import { capitalize, plural } from '../../lib/utils'

const MERIT_STATUSES = ['active', 'allocated', 'expired']

const statusVariantMap: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'neutral'> = {
  active: 'success',
  allocated: 'warning',
  expired: 'neutral',
}

function getStatusVariant(status: string) {
  return statusVariantMap[status] || 'neutral'
}

export function MeritListPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()

  const [data, setData] = useState<AdmissionMeritEntryResponse[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)
  const [programFilter, setProgramFilter] = useState('')
  const [yearFilter, setYearFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchIdRef = useRef(0)

  const fetchMerit = useCallback(async () => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    try {
      const result = await admissionApi.listMeritEntries({
        page,
        size,
        program_id: programFilter ? Number(programFilter) : undefined,
        academic_year_id: yearFilter ? Number(yearFilter) : undefined,
        status: statusFilter || undefined,
      })
      if (fetchId === fetchIdRef.current) {
        setData(result.items)
        setTotal(result.total)
        setPages(result.pages)
        setPage(result.page)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load merit list')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [page, size, programFilter, yearFilter, statusFilter])

  useEffect(() => { fetchMerit() }, [fetchMerit])

  return (
    <div className="space-y-8 animate-fade-in-up">
      {/* Narrative header */}
      <div>
        <p className="text-sm font-medium text-[var(--color-brand-accent)] tracking-wide mb-1">Admissions</p>
        <h1 className="text-3xl lg:text-4xl font-extrabold text-[var(--color-text-primary)] tracking-tight leading-tight">
          Merit List
        </h1>
        <p className="text-base text-[var(--color-text-tertiary)] mt-2 max-w-xl">
          {total > 0
            ? `${plural(total, 'ranked applicant')} across programs and academic years.`
            : 'Ranked applicants by program and academic year. Merit entries appear once applications are scored.'}
        </p>
      </div>

      {/* Filters bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <Input
            placeholder="Program ID"
            value={programFilter}
            onChange={(e) => { setProgramFilter(e.target.value); setPage(1) }}
            className="w-32"
          />
          <Input
            placeholder="Academic Year ID"
            value={yearFilter}
            onChange={(e) => { setYearFilter(e.target.value); setPage(1) }}
            className="w-40"
          />
          <Select
            options={[
              { value: '', label: 'All statuses' },
              ...MERIT_STATUSES.map((s) => ({ value: s, label: capitalize(s) })),
            ]}
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
          />
        </div>
        <Button variant="outline" onClick={() => { setProgramFilter(''); setYearFilter(''); setStatusFilter(''); setPage(1) }}>
          Reset filters
        </Button>
      </div>

      {/* Data table area */}
      <div className="bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] overflow-hidden">
        {loading ? (
          <Table columns={[]} data={[]} loading={true} keyExtractor={() => ''} emptyMessage="" />
        ) : error ? (
          <ErrorState message={error} onRetry={fetchMerit} />
        ) : data.length === 0 ? (
          <div className="p-8">
            <EmptyState
              title="No merit entries"
              description="Ranked applicants will appear here once admissions scoring is completed."
            />
          </div>
        ) : (
          <>
            <Table
              columns={[
                { key: 'rank', header: 'Rank', render: (m: AdmissionMeritEntryResponse) => (
                  <span className="font-semibold text-[var(--color-text-primary)]">#{m.rank}</span>
                )},
                { key: 'application_id', header: 'Application', render: (m: AdmissionMeritEntryResponse) => (
                  <button
                    className="font-medium text-[var(--color-brand-accent)] hover:underline"
                    onClick={(e) => { e.stopPropagation(); navigate(`/admissions/${m.application_id}`) }}
                  >
                    #{m.application_id}
                  </button>
                )},
                { key: 'total_score', header: 'Score', render: (m: AdmissionMeritEntryResponse) => (
                  <span className="tabular-nums">{m.total_score.toFixed(1)}</span>
                )},
                { key: 'category', header: 'Category', render: (m: AdmissionMeritEntryResponse) => m.category || '-' },
                { key: 'status', header: 'Status', render: (m: AdmissionMeritEntryResponse) => (
                  <StatusBadge status={m.status} variant={getStatusVariant(m.status)} />
                )},
              ]}
              data={data}
              keyExtractor={(m) => m.id}
              emptyMessage="No merit entries found"
              onRowClick={(m) => navigate(`/admissions/${m.application_id}`)}
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

export default MeritListPage
