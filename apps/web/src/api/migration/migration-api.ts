import { api, getAccessToken } from '../client/http-client'

// ── Types ─────────────────────────────────────────────────────────────

export const MIGRATION_STATUSES = [
  'DRAFT',
  'DISCOVERING',
  'MAPPING',
  'VALIDATING',
  'READY',
  'IMPORTING',
  'RECONCILING',
  'COMPLETED',
  'FAILED',
  'CANCELLED',
  'ROLLED_BACK',
] as const

export type MigrationStatus = (typeof MIGRATION_STATUSES)[number]

export interface MappingEntry {
  target: string
  confidence: string
  reason: string
  transforms: Array<{ op: string; [k: string]: unknown }>
}

export interface MigrationProject {
  id: number
  campus_id: number | null
  name: string
  source_system: string
  description: string | null
  status: MigrationStatus
  original_filename: string | null
  file_mime: string | null
  file_size: number
  row_count: number
  discovery: {
    record_count: number
    columns: Array<Record<string, unknown>>
    suggestions: Array<{
      source_field: string
      target_field: string
      confidence: string
      reason: string
    }>
    entities: string[]
  } | null
  mapping: Record<string, MappingEntry> | null
  validation: {
    blocking: number
    warnings: number
    info: number
    total: number
    samples: Array<Record<string, unknown>>
    categories: Record<string, number>
    is_ready: boolean
    validated_at: string
  } | null
  reconciliation: {
    source_records: number
    target_records: number
    created: number
    updated: number
    skipped: number
    rejected: number
    duplicates: number
    warnings: number
    run_id: number | null
    run_status: string | null
    entities: string[]
    reconciled_at: string
  } | null
  records_processed: number
  records_imported: number
  records_updated: number
  records_skipped: number
  records_rejected: number
  warnings: number
  operator_id: number | null
  run_id: number | null
  job_id: number | null
  created_at: string
  updated_at: string
  last_activity_at: string | null
  started_at: string | null
  completed_at: string | null
}

export interface MigrationProjectPage {
  items: MigrationProject[]
  total: number
  page: number
  size: number
  pages: number
}

export type PreviewAction = 'CREATE' | 'UPDATE' | 'SKIP' | 'ERROR'

export interface PreviewRow {
  row: number
  before: Record<string, unknown>
  after: Record<string, unknown>
  status: string
  action: PreviewAction
  action_reason: string | null
}

export interface PreviewResult {
  total: number
  limit: number
  rows: PreviewRow[]
  mapping: Record<string, MappingEntry> | null
}

export interface ImportProgress {
  project_id: number
  status: MigrationStatus
  records_processed: number
  records_imported: number
  records_updated: number
  records_skipped: number
  records_rejected: number
  warnings: number
  row_count: number
  job: { id: number; status: string; progress: number; last_error: string | null } | null
}

// ── Client ────────────────────────────────────────────────────────────

export const migrationApi = {
  list: (params?: { status?: string; skip?: number; limit?: number }) =>
    api.get<MigrationProjectPage>('/migration/projects', params),

  get: (projectId: number) =>
    api.get<MigrationProject>(`/migration/projects/${projectId}`),

  /**
   * Create a project from an uploaded source file (multipart).  The shared
   * http-client always sends JSON, so the upload goes through raw fetch with
   * FormData and the auth token attached.
   */
  create: async (
    payload: { name: string; source_system: string; description?: string },
    file: File
  ): Promise<MigrationProject> => {
    const form = new FormData()
    form.append('name', payload.name)
    form.append('source_system', payload.source_system)
    if (payload.description) form.append('description', payload.description)
    form.append('file', file)

    const res = await fetch('/migration/projects', {
      method: 'POST',
      headers: getAccessToken() ? { Authorization: `Bearer ${getAccessToken()}` } : undefined,
      body: form,
    })
    if (!res.ok) {
      const body = await res.json().catch(() => null)
      throw { status: res.status, detail: body?.detail || `HTTP ${res.status}` }
    }
    return res.json()
  },

  saveMapping: (projectId: number, mapping: Record<string, MappingEntry>) =>
    api.put<MigrationProject>(`/migration/projects/${projectId}/mapping`, { mapping }),

  validate: (projectId: number) =>
    api.post<{
      blocking: number
      warnings: number
      info: number
      total: number
      samples: Array<Record<string, unknown>>
      categories: Record<string, number>
      is_ready: boolean
      validated_at: string
    }>(`/migration/projects/${projectId}/validate`),

  preview: (projectId: number, limit = 10) =>
    api.get<PreviewResult>(`/migration/projects/${projectId}/preview`, { limit }),

  startImport: (projectId: number) =>
    api.post<MigrationProject>(`/migration/projects/${projectId}/import`),

  progress: (projectId: number) =>
    api.get<ImportProgress>(`/migration/projects/${projectId}/progress`),

  reconcile: (projectId: number) =>
    api.get<MigrationProject['reconciliation']>(`/migration/projects/${projectId}/reconcile`),

  report: async (projectId: number): Promise<string> => {
    const res = await fetch(`/migration/projects/${projectId}/report`, {
      headers: getAccessToken() ? { Authorization: `Bearer ${getAccessToken()}` } : undefined,
    })
    if (!res.ok) throw { status: res.status, detail: `HTTP ${res.status}` }
    return res.text()
  },

  /** Download a report variant (txt | csv | json) as a Blob. */
  reportBlob: async (
    projectId: number,
    format: 'txt' | 'csv' | 'json'
  ): Promise<{ blob: Blob; filename: string }> => {
    const path = format === 'txt' ? 'report' : `report.${format}`
    const res = await fetch(`/migration/projects/${projectId}/${path}`, {
      headers: getAccessToken() ? { Authorization: `Bearer ${getAccessToken()}` } : undefined,
    })
    if (!res.ok) throw { status: res.status, detail: `HTTP ${res.status}` }
    return {
      blob: await res.blob(),
      filename: `migration-${projectId}-report.${format === 'txt' ? 'txt' : format}`,
    }
  },

  cancel: (projectId: number) =>
    api.post<MigrationProject>(`/migration/projects/${projectId}/cancel`),

  rollback: (projectId: number) =>
    api.post<{ records_removed: number }>(`/migration/projects/${projectId}/rollback`),
}

// ── Presentation helpers ──────────────────────────────────────────────

export const MIGRATION_STATUS_STYLES: Record<string, string> = {
  DRAFT: 'border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[var(--color-text-muted)]',
  DISCOVERING: 'border-[var(--color-info)]/30 bg-[var(--color-info)]/10 text-[var(--color-info)]',
  MAPPING: 'border-[var(--color-info)]/30 bg-[var(--color-info)]/10 text-[var(--color-info)]',
  VALIDATING: 'border-[var(--color-warning)]/30 bg-[var(--color-warning)]/10 text-[var(--color-warning)]',
  READY: 'border-[var(--color-success)]/30 bg-[var(--color-success)]/10 text-[var(--color-success)]',
  IMPORTING: 'border-[var(--color-brand-accent)]/30 bg-[var(--color-brand-accent)]/10 text-[var(--color-brand-accent)]',
  RECONCILING: 'border-[var(--color-brand-accent)]/30 bg-[var(--color-brand-accent)]/10 text-[var(--color-brand-accent)]',
  COMPLETED: 'border-[var(--color-success)]/40 bg-[var(--color-success)]/15 text-[var(--color-success)]',
  FAILED: 'border-[var(--color-danger)]/30 bg-[var(--color-danger)]/10 text-[var(--color-danger)]',
  CANCELLED: 'border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[var(--color-text-muted)]',
  ROLLED_BACK: 'border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[var(--color-text-muted)]',
}

export const MIGRATION_STATUS_LABELS: Record<string, string> = {
  DRAFT: 'Draft',
  DISCOVERING: 'Discovering',
  MAPPING: 'Mapping',
  VALIDATING: 'Validating',
  READY: 'Ready',
  IMPORTING: 'Importing',
  RECONCILING: 'Reconciling',
  COMPLETED: 'Completed',
  FAILED: 'Failed',
  CANCELLED: 'Cancelled',
  ROLLED_BACK: 'Rolled Back',
}

export const SOURCE_SYSTEMS = [
  'Generic CSV',
  'PowerSchool-style export',
  'Legacy ERP export',
  'Student IS export',
]
