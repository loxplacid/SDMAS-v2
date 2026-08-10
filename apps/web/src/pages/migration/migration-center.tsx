import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  MIGRATION_STATUS_LABELS,
  MIGRATION_STATUS_STYLES,
  migrationApi,
  type MigrationProject,
} from '../../api/migration/migration-api'
import {
  Badge,
  Button,
  EmptyState,
  PageHeader,
  Skeleton,
} from '../../components/ui'
import { cn, formatDateTime, plural } from '../../lib/utils'

// ── Status summary header (D2.14) ─────────────────────────────────────

const STATUS_TILES = [
  { status: 'READY', label: 'Ready to import', accent: 'text-[var(--color-success)]' },
  { status: 'IMPORTING', label: 'Importing', accent: 'text-[var(--color-brand-accent)]' },
  { status: 'FAILED', label: 'Failed', accent: 'text-[var(--color-danger)]' },
  { status: 'COMPLETED', label: 'Completed', accent: 'text-[var(--color-success)]' },
] as const

function StatusTiles({ projects }: { projects: MigrationProject[] }) {
  const counts = useMemo(() => {
    const map: Record<string, number> = {}
    for (const p of projects) map[p.status] = (map[p.status] || 0) + 1
    return map
  }, [projects])

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {STATUS_TILES.map((tile, i) => (
        <div
          key={tile.status}
          className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 animate-fade-in-up"
          style={{ animationDelay: `${i * 50}ms`, animationFillMode: 'both' }}
        >
          <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-tertiary)]">
            {tile.label}
          </p>
          <p className={cn('mt-1.5 text-2xl font-bold tabular-nums leading-none', tile.accent)}>
            {counts[tile.status] || 0}
          </p>
        </div>
      ))}
    </div>
  )
}

function MigrationSkeleton() {
  return (
    <div className="space-y-6 animate-fade-in" aria-busy="true" aria-label="Loading migration center">
      <div className="space-y-3">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96" />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-20 rounded-2xl" />)}
      </div>
      <div className="space-y-2">
        {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────

export function MigrationCenterPage() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<MigrationProject[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const page = await migrationApi.list({ limit: 100 })
      setProjects(page.items)
    } catch (e: any) {
      setError(e?.detail || 'Migrations could not be loaded.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const summary = useMemo(() => {
    const totals = projects.reduce(
      (acc, p) => {
        acc.rows += p.row_count
        acc.imported += p.records_imported
        acc.rejected += p.records_rejected
        return acc
      },
      { rows: 0, imported: 0, rejected: 0 }
    )
    return totals
  }, [projects])

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Administration"
        title="Data Migration"
        subtitle="Bring your institution's data from an existing school management system into SDMAS — safely, with full audit trail."
        actions={
          <Button onClick={() => navigate('/migration/new')}>New Migration</Button>
        }
      />

      {loading ? (
        <MigrationSkeleton />
      ) : error ? (
        <EmptyState
          icon={
            <svg className="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            </svg>
          }
          title="Migrations couldn't be loaded"
          description={error}
          action={{ label: 'Retry', onClick: load }}
        />
      ) : projects.length === 0 ? (
        <EmptyState
          icon={
            <svg className="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          }
          title="No migrations yet"
          description="No data has been migrated into SDMAS. Start by uploading a legacy export — we'll discover its columns and suggest a field mapping."
          action={{ label: 'Start a migration', onClick: () => navigate('/migration/new') }}
        />
      ) : (
        <>
          <StatusTiles projects={projects} />

          {/* Sales summary strip (D2.14) */}
          <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-sm text-[var(--color-text-muted)] flex flex-wrap gap-x-6 gap-y-2 animate-fade-in-up">
            <span>
              <strong className="text-[var(--color-text-primary)] tabular-nums">
                {plural(summary.rows, 'source record')}
              </strong>{' '}
              discovered across {plural(projects.length, 'migration')}
            </span>
            <span>
              <strong className="text-[var(--color-success)] tabular-nums">
                {plural(summary.imported, 'record')}
              </strong>{' '}
              imported
            </span>
            {summary.rejected > 0 && (
              <span>
                <strong className="text-[var(--color-danger)] tabular-nums">
                  {plural(summary.rejected, 'record')}
                </strong>{' '}
                rejected
              </span>
            )}
          </div>

          {/* Projects table */}
          <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden animate-fade-in-up">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)] text-left text-[11px] uppercase tracking-wider text-[var(--color-text-tertiary)]">
                    <th className="px-4 py-3 font-semibold">Migration</th>
                    <th className="px-4 py-3 font-semibold">Status</th>
                    <th className="px-4 py-3 font-semibold text-right">Records</th>
                    <th className="px-4 py-3 font-semibold text-right">Imported</th>
                    <th className="px-4 py-3 font-semibold text-right">Rejected</th>
                    <th className="px-4 py-3 font-semibold">Source</th>
                    <th className="px-4 py-3 font-semibold">Last activity</th>
                  </tr>
                </thead>
                <tbody>
                  {projects.map((p) => (
                    <tr
                      key={p.id}
                      onClick={() => navigate(`/migration/${p.id}`)}
                      className={cn(
                        'border-b border-[var(--color-border)]/60 last:border-0 cursor-pointer',
                        'motion-safe:transition-colors hover:bg-[var(--color-surface-hover)]'
                      )}
                    >
                      <td className="px-4 py-3">
                        <p className="font-medium text-[var(--color-text-primary)]">{p.name}</p>
                        <p className="text-xs text-[var(--color-text-tertiary)]">
                          {p.original_filename || `Migration #${p.id}`}
                        </p>
                      </td>
                      <td className="px-4 py-3">
                        <Badge className={MIGRATION_STATUS_STYLES[p.status] || ''}>
                          {MIGRATION_STATUS_LABELS[p.status] || p.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-[var(--color-text-primary)]">
                        {p.row_count.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-[var(--color-success)]">
                        {p.records_imported.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-[var(--color-danger)]">
                        {p.records_rejected > 0 ? p.records_rejected.toLocaleString() : '—'}
                      </td>
                      <td className="px-4 py-3 text-[var(--color-text-muted)]">{p.source_system}</td>
                      <td className="px-4 py-3 text-xs text-[var(--color-text-tertiary)]">
                        {p.last_activity_at ? formatDateTime(p.last_activity_at) : formatDateTime(p.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
