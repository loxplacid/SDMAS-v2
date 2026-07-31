import { useState, useEffect, useCallback, useRef } from 'react'
import { auditLogApi } from '../../api/audit/audit-api'
import type { AuditLogEntry } from '../../api/audit/audit-api'
import { Card, Table, Pagination, Input, Select, Button, Badge, ErrorState, Drawer, Tooltip } from '../../components/ui'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { formatDateTime, cn } from '../../lib/utils'

// ── Helpers ──

const ACTION_VARIANTS: Record<string, 'info' | 'success' | 'danger' | 'warning'> = {
  CREATE: 'success',
  UPDATE: 'info',
  DELETE: 'danger',
}

function ActionBadge({ action }: { action: string }) {
  return (
    <Badge variant={ACTION_VARIANTS[action] || 'default'}>
      {action}
    </Badge>
  )
}

function formatDetails(details: unknown): string {
  if (!details) return '-'
  if (typeof details === 'string') {
    try {
      return JSON.stringify(JSON.parse(details), null, 2)
    } catch {
      return details
    }
  }
  return JSON.stringify(details, null, 2)
}

function extractUserAgent(entry: AuditLogEntry): string {
  if (entry.user_agent) {
    const ua = entry.user_agent
    if (ua.startsWith('python-httpx')) return 'API'
    if (ua.includes('Mozilla')) {
      const match = ua.match(/\(([^)]+)\)/)
      return match ? match[1].split(';')[0].trim() : 'Browser'
    }
    return ua.split('/')[0] || ua
  }
  return '-'
}

// ── Page Component ──

export function AuditLogViewerPage() {

  // ── Data state ──
  const [entries, setEntries] = useState<AuditLogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(50)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // ── Filter state ──
  const [actionFilter, setActionFilter] = useState('')
  const [resourceFilter, setResourceFilter] = useState('')
  const [userIdFilter, setUserIdFilter] = useState('')
  const [startDateFilter, setStartDateFilter] = useState('')
  const [endDateFilter, setEndDateFilter] = useState('')

  // ── Expanded row state ──
  const [expandedId, setExpandedId] = useState<number | null>(null)

  // ── Detail modal state ──
  const [detailEntry, setDetailEntry] = useState<AuditLogEntry | null>(null)

  const fetchIdRef = useRef(0)

  const fetch = useCallback(async (params: {
    page?: number; size?: number; action?: string; resource_type?: string;
    user_id?: number; start_date?: string; end_date?: string
  }) => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    setError(null)
    try {
      const result = await auditLogApi.list(params)
      if (fetchId === fetchIdRef.current) {
        setEntries(result.items)
        setTotal(result.total)
        setPages(result.pages)
        setPage(result.page)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) {
        setError(err?.detail || 'Failed to load audit logs')
      }
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch({
      page,
      size,
      action: actionFilter || undefined,
      resource_type: resourceFilter || undefined,
      user_id: userIdFilter ? Number(userIdFilter) : undefined,
      start_date: startDateFilter || undefined,
      end_date: endDateFilter || undefined,
    })
  }, [page, size, actionFilter, resourceFilter, userIdFilter, startDateFilter, endDateFilter, fetch])

  const toggleExpand = (id: number) => {
    setExpandedId(expandedId === id ? null : id)
  }

  const openDetail = (entry: AuditLogEntry) => {
    setDetailEntry(entry)
  }

  // ── Keyboard shortcut: refresh ──
  useKeyboardShortcut({
    'r': () => fetch({ page, size, action: actionFilter || undefined, resource_type: resourceFilter || undefined }),
  }, [page, size, actionFilter, resourceFilter, fetch])

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-[var(--color-brand-accent)] tracking-wide mb-1">
            Administration
          </p>
          <h1 className="text-2xl font-bold text-[var(--color-text-primary)] tracking-tight">
            Audit Logs
          </h1>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-1">
            {total} event{total !== 1 ? 's' : ''} &middot; Immutable record of all mutating operations
          </p>
        </div>
        <Button variant="outline" onClick={() => fetch({ page, size, action: actionFilter || undefined, resource_type: resourceFilter || undefined })}>
          <svg className="h-4 w-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh
          <kbd className="ml-2 hidden sm:inline-flex items-center px-1.5 py-0.5 rounded bg-[var(--color-surface-hover)] text-[10px] font-medium text-[var(--color-text-muted)]">R</kbd>
        </Button>
      </div>

      {/* Filters */}
      <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <Select
            label="Action"
            placeholder="All actions"
            value={actionFilter}
            onChange={(e) => { setActionFilter(e.target.value); setPage(1) }}
            options={[
              { value: 'CREATE', label: 'CREATE' },
              { value: 'UPDATE', label: 'UPDATE' },
              { value: 'DELETE', label: 'DELETE' },
            ]}
          />
          <Input
            label="Resource Type"
            placeholder="e.g. student, fee"
            value={resourceFilter}
            onChange={(e) => { setResourceFilter(e.target.value); setPage(1) }}
          />
          <Input
            label="User ID"
            placeholder="Filter by actor"
            type="number"
            value={userIdFilter}
            onChange={(e) => { setUserIdFilter(e.target.value); setPage(1) }}
          />
          <Input
            label="Start Date"
            type="date"
            value={startDateFilter}
            onChange={(e) => { setStartDateFilter(e.target.value); setPage(1) }}
          />
          <Input
            label="End Date"
            type="date"
            value={endDateFilter}
            onChange={(e) => { setEndDateFilter(e.target.value); setPage(1) }}
          />
        </div>
      </Card>

      {/* Table */}
      <Card className="overflow-hidden">
        {error ? (
          <ErrorState message={error} onRetry={() => fetch({ page, size })} />
        ) : (
          <>
            <Table
              columns={[
                {
                  key: 'action',
                  header: 'Action',
                  render: (e: AuditLogEntry) => <ActionBadge action={e.action} />,
                  className: 'w-24',
                },
                {
                  key: 'resource_type',
                  header: 'Resource',
                  render: (e: AuditLogEntry) => (
                    <span className="font-medium text-[var(--color-text-primary)]">
                      {e.resource_type}
                      {e.resource_id ? <span className="text-[var(--color-text-muted)]"> #{e.resource_id}</span> : null}
                    </span>
                  ),
                },
                {
                  key: 'username',
                  header: 'Actor',
                  render: (e: AuditLogEntry) => (
                    <span className={cn(!e.username && 'text-[var(--color-text-muted)] italic')}>
                      {e.username || 'Anonymous'}
                    </span>
                  ),
                  hideOnMobile: true,
                },
                {
                  key: 'ip_address',
                  header: 'IP',
                  render: (e: AuditLogEntry) => (
                    <span className="text-[var(--color-text-muted)] text-xs font-mono">
                      {e.ip_address || '-'}
                    </span>
                  ),
                  hideOnMobile: true,
                },
                {
                  key: 'user_agent',
                  header: 'Source',
                  render: (e: AuditLogEntry) => (
                    <span className="text-xs text-[var(--color-text-muted)]">
                      {extractUserAgent(e)}
                    </span>
                  ),
                  hideOnMobile: true,
                },
                {
                  key: 'created_at',
                  header: 'Timestamp',
                  render: (e: AuditLogEntry) => (
                    <span className="text-sm text-[var(--color-text-secondary)] whitespace-nowrap">
                      {formatDateTime(e.created_at)}
                    </span>
                  ),
                },                  {
                    key: 'details',
                    header: '',
                    render: (e: AuditLogEntry) => (
                      <div className="flex gap-1">
                        <Tooltip content="Toggle details">
                          <button
                            onClick={(ev) => { ev.stopPropagation(); toggleExpand(e.id) }}
                            className="p-1.5 rounded-lg hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors"
                          >
                            <svg
                              className={cn('h-4 w-4 transition-transform', expandedId === e.id && 'rotate-90')}
                              fill="none" stroke="currentColor" viewBox="0 0 24 24"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                          </button>
                        </Tooltip>
                        <Tooltip content="View full details">
                          <button
                            onClick={(ev) => { ev.stopPropagation(); openDetail(e) }}
                            className="p-1.5 rounded-lg hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors"
                          >
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                            </svg>
                          </button>
                        </Tooltip>
                      </div>
                    ),
                    className: 'w-20 text-right',
                  },
              ]}
              data={entries}
              keyExtractor={(e) => e.id}
              loading={loading}
              emptyMessage="No audit events match your filters."
              onRowClick={(e) => toggleExpand(e.id)}
            />

            {/* Expandable detail rows */}
            {expandedId !== null && (
              <div className="border-t border-[var(--color-border)] bg-[var(--color-bg)]/50">
                {(() => {
                  const entry = entries.find((e) => e.id === expandedId)
                  if (!entry) return null
                  return (
                    <div className="p-4 sm:p-6 space-y-3 animate-slide-down text-sm">
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        <DetailField label="Event ID" value={`#${entry.id}`} />
                        <DetailField label="IP Address" value={entry.ip_address || '-'} />
                        <DetailField label="User Agent" value={entry.user_agent || '-'} />
                        <DetailField label="Campus" value={entry.campus_id ? `Campus #${entry.campus_id}` : 'N/A'} />
                        <DetailField label="Resource ID" value={entry.resource_id || '-'} />
                        <DetailField label="Timestamp" value={formatDateTime(entry.created_at)} />
                      </div>
                      {entry.details && (
                        <div>
                          <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-1.5">
                            Details
                          </p>
                          <pre className="text-xs font-mono text-[var(--color-text-secondary)] bg-[var(--color-surface)] rounded-lg p-3 overflow-x-auto max-h-48 overflow-y-auto border border-[var(--color-border)]">
                            {formatDetails(entry.details)}
                          </pre>
                        </div>
                      )}
                    </div>
                  )
                })()}
              </div>
            )}

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
      </Card>

      {/* Detail Drawer */}
      <Drawer
        open={detailEntry !== null}
        onClose={() => setDetailEntry(null)}
        title={`Audit Event #${detailEntry?.id || ''}`}
        size="lg"
        side="right"
      >
        {detailEntry && (
          <div className="space-y-6">
            <div className="flex items-center gap-3">
              <ActionBadge action={detailEntry.action} />
              <span className="text-sm font-medium text-[var(--color-text-primary)]">
                {detailEntry.resource_type}
                {detailEntry.resource_id ? <span className="text-[var(--color-text-muted)]"> #{detailEntry.resource_id}</span> : null}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <DetailField label="Actor" value={detailEntry.username || 'Anonymous'} />
              <DetailField label="Actor ID" value={detailEntry.user_id ? String(detailEntry.user_id) : '-'} />
              <DetailField label="IP Address" value={detailEntry.ip_address || '-'} />
              <DetailField label="User Agent" value={detailEntry.user_agent || '-'} />
              <DetailField label="Campus ID" value={detailEntry.campus_id ? String(detailEntry.campus_id) : '-'} />
              <DetailField label="Resource ID" value={detailEntry.resource_id || '-'} />
            </div>

            <div>
              <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-2">
                Event Details
              </p>
              <pre className="text-xs font-mono text-[var(--color-text-secondary)] bg-[var(--color-bg)] rounded-lg p-4 overflow-x-auto max-h-64 overflow-y-auto border border-[var(--color-border)]">
                {formatDetails(detailEntry.details)}
              </pre>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  )
}

function DetailField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-0.5">
        {label}
      </p>
      <p className="text-sm text-[var(--color-text-primary)] break-words">{value || '-'}</p>
    </div>
  )
}

export default AuditLogViewerPage
