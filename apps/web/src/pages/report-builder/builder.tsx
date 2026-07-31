import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  reportDefinitionApi,
  reportExecuteApi,
  savedReportApi,
  exportJobApi,
} from '../../api/report-builder/report-builder-api'
import type {
  ReportDefinitionInfo,
  ReportExecuteResponse,
  ReportFilterSchema,
  ReportColumnSchema,
} from '../../api/report-builder/report-builder-api'
import {
  PageHeader,
  Card,
  Button,
  Table,
  Input,
  Select,
  Modal,
  Loading,
  ErrorState,
  useToast,
} from '../../components/ui'
import { formatDate } from '../../lib/utils'

export function ReportBuilderPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [searchParams] = useSearchParams()
  const categoryFilter = searchParams.get('category')

  const [definitions, setDefinitions] = useState<ReportDefinitionInfo[]>([])
  const [selectedDefId, setSelectedDefId] = useState<string>('')
  const [definitionsLoading, setDefinitionsLoading] = useState(true)
  const [definitionsError, setDefinitionsError] = useState<string | null>(null)

  const [filterValues, setFilterValues] = useState<Record<string, string>>({})
  const [executing, setExecuting] = useState(false)
  const [executeError, setExecuteError] = useState<string | null>(null)

  const [result, setResult] = useState<ReportExecuteResponse | null>(null)
  const [executedDefId, setExecutedDefId] = useState<number | null>(null)

  const [saveModalOpen, setSaveModalOpen] = useState(false)
  const [saveName, setSaveName] = useState('')
  const [saving, setSaving] = useState(false)

  const [exporting, setExporting] = useState<string | null>(null)
  const fetchIdRef = useRef(0)

  useEffect(() => {
    reportDefinitionApi.list({ category: categoryFilter || undefined } as any)
      .then((defs) => {
        setDefinitions(defs)
        if (defs.length === 1) {
          setSelectedDefId(String(defs[0].id))
        }
      })
      .catch((err: any) => setDefinitionsError(err?.detail || 'Failed to load report definitions'))
      .finally(() => setDefinitionsLoading(false))
  }, [categoryFilter])

  const selectedDef = definitions.find((d) => String(d.id) === selectedDefId)

  useEffect(() => {
    if (selectedDef?.default_params) {
      const initial: Record<string, string> = {}
      for (const [k, v] of Object.entries(selectedDef.default_params)) {
        initial[k] = String(v ?? '')
      }
      setFilterValues((prev) => ({ ...initial, ...prev }))
    }
  }, [selectedDefId])

  const handleFilterChange = useCallback((key: string, value: string) => {
    setFilterValues((prev) => ({ ...prev, [key]: value }))
  }, [])

  const runReport = useCallback(async () => {
    if (!selectedDef) return
    const fetchId = ++fetchIdRef.current
    setExecuting(true)
    setExecuteError(null)
    setResult(null)
    setExecutedDefId(null)

    try {
      const params: Record<string, any> = {}
      for (const f of selectedDef.filters) {
        const val = filterValues[f.key]
        if (val !== undefined && val !== '') {
          params[f.key] = f.type === 'number' ? Number(val) : val
        }
      }
      const resp = await reportExecuteApi.execute({
        report_definition_id: selectedDef.id,
        params,
      })
      if (fetchId === fetchIdRef.current) {
        setResult(resp)
        setExecutedDefId(selectedDef.id)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) {
        setExecuteError(err?.detail || 'Failed to execute report')
      }
    } finally {
      if (fetchId === fetchIdRef.current) setExecuting(false)
    }
  }, [selectedDef, filterValues])

  const handleSave = useCallback(async () => {
    if (!selectedDef || !saveName.trim()) return
    setSaving(true)
    try {
      await savedReportApi.create({
        report_definition_id: selectedDef.id,
        name: saveName.trim(),
        params: filterValues,
      })
      showToast('Report saved successfully', 'success')
      setSaveModalOpen(false)
      setSaveName('')
    } catch (err: any) {
      showToast(err?.detail || 'Failed to save report', 'error')
    } finally {
      setSaving(false)
    }
  }, [selectedDef, saveName, filterValues, showToast])

  const handleExport = useCallback(async (format: string) => {
    if (!selectedDef) return
    setExporting(format)
    try {
      const job = await exportJobApi.create({
        report_definition_id: selectedDef.id,
        params: filterValues,
        format,
      })
      showToast(`${format.toUpperCase()} export started`, 'success')
      navigate(`/reports/builder/exports?highlight=${job.id}`)
    } catch (err: any) {
      showToast(err?.detail || `Failed to start ${format} export`, 'error')
    } finally {
      setExporting(null)
    }
  }, [selectedDef, filterValues, navigate, showToast])

  function renderFilterInput(filter: ReportFilterSchema) {
    const value = filterValues[filter.key] ?? ''

    if (filter.options && filter.options.length > 0) {
      return (
        <Select
          key={filter.key}
          label={filter.label}
          options={filter.options}
          value={value}
          placeholder={filter.placeholder || `Select ${filter.label}`}
          onChange={(e) => handleFilterChange(filter.key, e.target.value)}
        />
      )
    }

    switch (filter.type) {
      case 'text':
        return (
          <Input
            key={filter.key}
            label={filter.label}
            placeholder={filter.placeholder || `Enter ${filter.label}`}
            value={value}
            onChange={(e) => handleFilterChange(filter.key, e.target.value)}
          />
        )
      case 'number':
        return (
          <Input
            key={filter.key}
            label={filter.label}
            type="number"
            placeholder={filter.placeholder || `Enter ${filter.label}`}
            value={value}
            onChange={(e) => handleFilterChange(filter.key, e.target.value)}
          />
        )
      case 'date':
        return (
          <Input
            key={filter.key}
            label={filter.label}
            type="date"
            value={value}
            onChange={(e) => handleFilterChange(filter.key, e.target.value)}
          />
        )
      default:
        return (
          <Input
            key={filter.key}
            label={filter.label}
            placeholder={filter.placeholder || `Enter ${filter.label}`}
            value={value}
            onChange={(e) => handleFilterChange(filter.key, e.target.value)}
          />
        )
    }
  }

  if (definitionsLoading) return <Loading text="Loading report definitions..." />
  if (definitionsError) return <ErrorState message={definitionsError} onRetry={() => window.location.reload()} />

  const tableColumns = result
    ? result.columns.map((col: ReportColumnSchema) => ({
        key: col.key,
        header: col.header,
      }))
    : []

  const tableData = result
    ? result.rows.map((row, i) => ({ ...row, _row_key: i }))
    : []

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        title="Report Builder"
        subtitle="Configure and run custom reports"
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={() => navigate('/reports/builder')}>
              Back to Hub
            </Button>
            <Button variant="secondary" size="sm" onClick={() => navigate('/reports/builder/saved')}>
              Saved Reports
            </Button>
            <Button variant="secondary" size="sm" onClick={() => navigate('/reports/builder/exports')}>
              Export Jobs
            </Button>
          </div>
        }
      />

      <Card title="Select Report">
        <div className="space-y-4">
          <Select
            label="Report Type"
            options={definitions.map((d) => ({ value: String(d.id), label: d.name }))}
            value={selectedDefId}
            placeholder="Select a report type"
            onChange={(e) => setSelectedDefId(e.target.value)}
          />
          {selectedDef?.description && (
            <p className="text-sm text-[var(--color-text-tertiary)]">{selectedDef.description}</p>
          )}
        </div>
      </Card>

      {selectedDef && selectedDef.filters.length > 0 && (
        <Card title="Filters">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {selectedDef.filters.map(renderFilterInput)}
          </div>
          <div className="mt-4">
            <Button onClick={runReport} loading={executing}>
              Run Report
            </Button>
          </div>
        </Card>
      )}

      {selectedDef && selectedDef.filters.length === 0 && (
        <div className="mt-4">
          <Button onClick={runReport} loading={executing}>
            Run Report
          </Button>
        </div>
      )}

      {executeError && <ErrorState message={executeError} onRetry={runReport} />}

      {executing && <div className="h-48 bg-[var(--color-surface)] rounded-xl animate-pulse" />}

      {result && (
        <>
          {Object.keys(result.summary).length > 0 && (
            <Card title="Summary">
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                {Object.entries(result.summary).map(([key, value]) => (
                  <div key={key}>
                    <p className="text-sm text-[var(--color-text-tertiary)] capitalize">
                      {key.replace(/_/g, ' ')}
                    </p>
                    <p className="text-2xl font-bold text-[var(--color-text-primary)]">
                      {String(value ?? '-')}
                    </p>
                  </div>
                ))}
              </div>
            </Card>
          )}

          <Card
            title="Results"
            subtitle={`${result.total_rows.toLocaleString()} row${result.total_rows !== 1 ? 's' : ''}`}
            actions={
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" onClick={() => setSaveModalOpen(true)}>
                  Save Report
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  loading={exporting === 'csv'}
                  onClick={() => handleExport('csv')}
                >
                  Export CSV
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  loading={exporting === 'excel'}
                  onClick={() => handleExport('excel')}
                >
                  Export Excel
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  loading={exporting === 'pdf'}
                  onClick={() => handleExport('pdf')}
                >
                  Export PDF
                </Button>
              </div>
            }
          >
            <Table
              columns={tableColumns}
              data={tableData}
              keyExtractor={(row: any) => row._row_key}
            />
          </Card>
        </>
      )}

      <Modal
        open={saveModalOpen}
        onClose={() => { setSaveModalOpen(false); setSaveName('') }}
        title="Save Report"
        size="sm"
        footer={
          <div className="flex gap-2 w-full justify-end">
            <Button variant="secondary" onClick={() => { setSaveModalOpen(false); setSaveName('') }}>
              Cancel
            </Button>
            <Button onClick={handleSave} loading={saving} disabled={!saveName.trim()}>
              Save
            </Button>
          </div>
        }
      >
        <Input
          label="Report Name"
          placeholder="My saved report"
          value={saveName}
          onChange={(e) => setSaveName(e.target.value)}
          autoFocus
        />
      </Modal>
    </div>
  )
}

export default ReportBuilderPage
