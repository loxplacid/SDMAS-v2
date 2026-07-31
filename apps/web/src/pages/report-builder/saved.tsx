import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { savedReportApi, reportDefinitionApi } from '../../api/report-builder/report-builder-api'
import type { SavedReportResponse, Page } from '../../api/report-builder/report-builder-api'
import { PageHeader, Card, Button, Table, Pagination, Loading, ErrorState } from '../../components/ui'
import { formatDate } from '../../lib/utils'

export function SavedReportsPage() {
  const navigate = useNavigate()

  const [data, setData] = useState<Page<SavedReportResponse> | null>(null)
  const [definitions, setDefinitions] = useState<Record<number, string>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)

  const size = 20

  const fetchSaved = useCallback(async () => {
    setLoading(true)
    try {
      const result = await savedReportApi.list({ page, size })
      setData(result)
      setError(null)

      const defIds = [...new Set(result.items.map((r) => r.report_definition_id))]
      if (defIds.length > 0) {
        const defs = await reportDefinitionApi.list()
        const defMap: Record<number, string> = {}
        for (const d of defs) {
          defMap[d.id] = d.name
        }
        setDefinitions(defMap)
      }
    } catch (err: any) {
      setError(err?.detail || 'Failed to load saved reports')
    } finally {
      setLoading(false)
    }
  }, [page])

  useEffect(() => {
    fetchSaved()
  }, [fetchSaved])

  const handleLoad = useCallback((report: SavedReportResponse) => {
    navigate(`/reports/builder/new?load=${report.id}`, {
      state: { savedReport: report },
    })
  }, [navigate])

  const columns = [
    { key: 'name', header: 'Name' },
    {
      key: 'report_definition_id',
      header: 'Report Type',
      render: (row: SavedReportResponse) => (
        <span className="text-sm text-[var(--color-text-primary)]">
          {definitions[row.report_definition_id] || `Report #${row.report_definition_id}`}
        </span>
      ),
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (row: SavedReportResponse) => (
        <span className="text-sm text-[var(--color-text-muted)]">{formatDate(row.created_at)}</span>
      ),
    },
    {
      key: 'actions',
      header: '',
      render: (row: SavedReportResponse) => (
        <Button
          variant="primary"
          size="xs"
          onClick={(e) => { e.stopPropagation(); handleLoad(row) }}
        >
          Load
        </Button>
      ),
    },
  ]

  if (loading && !data) return <Loading text="Loading saved reports..." />
  if (error && !data) return <ErrorState message={error} onRetry={fetchSaved} />

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        title="Saved Reports"
        subtitle="View and load your saved report configurations"
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={() => navigate('/reports/builder')}>
              Back to Builder
            </Button>
            <Button variant="secondary" size="sm" onClick={() => navigate('/reports/builder/exports')}>
              Export Jobs
            </Button>
          </div>
        }
      />

      <Card>
        <Table
          columns={columns}
          data={data?.items || []}
          keyExtractor={(row) => row.id}
          loading={loading}
          emptyMessage="No saved reports yet"
          onRowClick={handleLoad}
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

export default SavedReportsPage
