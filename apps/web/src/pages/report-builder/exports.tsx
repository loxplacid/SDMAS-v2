import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { exportJobApi } from '../../api/report-builder/report-builder-api'
import type { ExportJobResponse, Page } from '../../api/report-builder/report-builder-api'
import { PageHeader, Card, Button, Badge, Table, Pagination, Select, Loading, ErrorState, useToast } from '../../components/ui'
import { formatDateTime } from '../../lib/utils'
import type { BadgeVariant } from '../../components/ui'

const STATUS_BADGE: Record<string, BadgeVariant> = {
  pending: 'neutral',
  processing: 'warning',
  completed: 'success',
  failed: 'danger',
}

export function ExportJobsPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [searchParams] = useSearchParams()
  const highlightId = searchParams.get('highlight')

  const [data, setData] = useState<Page<ExportJobResponse> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [downloading, setDownloading] = useState<number | null>(null)
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const size = 20

  const fetchJobs = useCallback(async () => {
    try {
      const params: Record<string, any> = { page, size }
      if (statusFilter) params.status = statusFilter
      const result = await exportJobApi.list(params)
      setData(result)
      setError(null)
    } catch (err: any) {
      setError(err?.detail || 'Failed to load export jobs')
    } finally {
      setLoading(false)
    }
  }, [page, statusFilter])

  useEffect(() => {
    setLoading(true)
    fetchJobs()
  }, [fetchJobs])

  useEffect(() => {
    if (!data) return
    const hasActive = data.items.some((j) => j.status === 'pending' || j.status === 'processing')
    if (hasActive) {
      pollTimerRef.current = setTimeout(() => {
        fetchJobs()
      }, 3000)
    }
    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current)
    }
  }, [data, fetchJobs])

  const handleDownload = useCallback(async (id: number) => {
    setDownloading(id)
    try {
      const blob = await exportJobApi.download(id)
      const disposition = (blob as any)?.headers?.get?.('content-disposition') || ''
      const match = disposition.match(/filename="?(.+?)"?(?:;|$)/)
      const filename = match?.[1] || `export-${id}.csv`
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    } catch (err: any) {
      showToast(err?.detail || 'Failed to download export', 'error')
    } finally {
      setDownloading(null)
    }
  }, [showToast])

  const columns = [
    { key: 'id', header: 'ID' },
    {
      key: 'report_definition_id',
      header: 'Report',
      render: (row: ExportJobResponse) => (
        <span className="text-sm text-[var(--color-text-primary)]">
          Report #{row.report_definition_id}
        </span>
      ),
    },
    {
      key: 'format',
      header: 'Format',
      render: (row: ExportJobResponse) => (
        <Badge variant="info" size="sm">{row.format.toUpperCase()}</Badge>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row: ExportJobResponse) => (
        <Badge variant={STATUS_BADGE[row.status] || 'neutral'} size="sm" dot>
          {row.status}
        </Badge>
      ),
    },
    {
      key: 'progress',
      header: 'Progress',
      render: (row: ExportJobResponse) => {
        if (row.status === 'completed') return <span className="text-sm text-[var(--color-text-muted)]">100%</span>
        if (row.status === 'failed') return <span className="text-sm text-[var(--color-danger)]">Failed</span>
        return (
          <div className="flex items-center gap-2">
            <div className="w-24 h-1.5 bg-[var(--color-surface-hover)] rounded-full overflow-hidden">
              <div
                className="h-full bg-[var(--color-brand-accent)] rounded-full transition-all duration-500"
                style={{ width: `${Math.min(row.progress, 100)}%` }}
              />
            </div>
            <span className="text-xs text-[var(--color-text-tertiary)]">{row.progress}%</span>
          </div>
        )
      },
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (row: ExportJobResponse) => (
        <span className="text-sm text-[var(--color-text-muted)]">{formatDateTime(row.created_at)}</span>
      ),
    },
    {
      key: 'actions',
      header: '',
      render: (row: ExportJobResponse) => {
        if (row.status === 'completed') {
          return (
            <Button
              variant="secondary"
              size="xs"
              loading={downloading === row.id}
              onClick={(e) => { e.stopPropagation(); handleDownload(row.id) }}
            >
              Download
            </Button>
          )
        }
        if (row.status === 'failed') {
          return (
            <span className="text-xs text-[var(--color-danger)] max-w-[200px] truncate block" title={row.error_message || ''}>
              {row.error_message || 'Error'}
            </span>
          )
        }
        return null
      },
    },
  ]

  if (loading && !data) return <Loading text="Loading export jobs..." />
  if (error && !data) return <ErrorState message={error} onRetry={fetchJobs} />

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        title="Export Jobs"
        subtitle="Track and download your report exports"
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={() => navigate('/reports/builder')}>
              Back to Builder
            </Button>
            <Button variant="secondary" size="sm" onClick={() => navigate('/reports/builder/saved')}>
              Saved Reports
            </Button>
          </div>
        }
      />

      <Card>
        <div className="flex items-center gap-4 mb-4">
          <div className="w-48">
            <Select
              label="Status"
              options={[
                { value: '', label: 'All Statuses' },
                { value: 'pending', label: 'Pending' },
                { value: 'processing', label: 'Processing' },
                { value: 'completed', label: 'Completed' },
                { value: 'failed', label: 'Failed' },
              ]}
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
            />
          </div>
        </div>

        <Table
          columns={columns}
          data={data?.items || []}
          keyExtractor={(row) => row.id}
          loading={loading}
          emptyMessage="No export jobs found"
        />

        {data && (
          <Pagination
            page={data.page}
            size={data.size}
            total={data.total}
            pages={data.pages}
            onPageChange={setPage}
          />
        )}
      </Card>
    </div>
  )
}

export default ExportJobsPage
