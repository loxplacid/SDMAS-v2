import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ToastProvider } from '../components/ui/toast'

const getMock = vi.fn()
const previewMock = vi.fn()

vi.mock('../api/migration/migration-api', () => ({
  migrationApi: {
    get: (...args: unknown[]) => getMock(...args),
    create: vi.fn(),
    saveMapping: vi.fn(),
    validate: vi.fn(),
    preview: (...args: unknown[]) => previewMock(...args),
    progress: vi.fn(),
    startImport: vi.fn(),
    cancel: vi.fn(),
    reconcile: vi.fn(),
    report: vi.fn(),
    reportBlob: vi.fn(),
    rollback: vi.fn(),
  },
  MIGRATION_STATUS_LABELS: {
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
  },
  MIGRATION_STATUS_STYLES: {
    MAPPING: 'border-mapping',
    READY: 'border-ready',
    IMPORTING: 'border-importing',
    COMPLETED: 'border-completed',
  },
  SOURCE_SYSTEMS: ['Generic CSV', 'PowerSchool-style export'],
}))

const { MigrationWizardPage } = await import('../pages/migration/migration-wizard')

function makeProject(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
    campus_id: 1,
    name: 'PowerSchool 2026 export',
    source_system: 'PowerSchool-style export',
    description: null,
    status: 'MAPPING',
    original_filename: 'students.csv',
    file_mime: 'text/csv',
    file_size: 1024,
    row_count: 12420,
    discovery: {
      record_count: 12420,
      columns: [
        { name: 'student_number', inferred_type: 'string', null_rate: 0, distinct_ratio: 0.99, is_duplicate_candidate: true, sample_values: ['S1001'] },
        { name: 'full_name', inferred_type: 'string', null_rate: 0.02, distinct_ratio: 0.98, is_duplicate_candidate: false, sample_values: ['John Doe'] },
      ],
      suggestions: [
        { source_field: 'student_number', target_field: 'student_number', confidence: 'high', reason: 'Identifier-like' },
        { source_field: 'full_name', target_field: 'full_name', confidence: 'high', reason: 'Name-like' },
      ],
      entities: ['students', 'academic', 'attendance', 'fees'],
    },
    mapping: null,
    validation: null,
    reconciliation: null,
    records_processed: 0,
    records_imported: 0,
    records_updated: 0,
    records_skipped: 0,
    records_rejected: 0,
    warnings: 0,
    operator_id: 1,
    run_id: null,
    job_id: null,
    created_at: '2026-08-10T09:00:00Z',
    updated_at: '2026-08-10T09:00:00Z',
    last_activity_at: '2026-08-10T09:00:00Z',
    started_at: null,
    completed_at: null,
    ...overrides,
  }
}

function renderWizard(path = '/migration/new') {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/migration/new" element={<MigrationWizardPage />} />
          <Route path="/migration/:id" element={<MigrationWizardPage />} />
        </Routes>
      </MemoryRouter>
    </ToastProvider>
  )
}

describe('Migration Wizard (D2)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the Source step for a new migration (CSV, XLSX, JSON, JSONL)', () => {
    renderWizard()

    expect(screen.getByText('New data migration')).toBeInTheDocument()
    expect(screen.getByLabelText('Migration name')).toBeInTheDocument()
    expect(screen.getByLabelText('Source system')).toBeInTheDocument()
    expect(screen.getByLabelText('Description (optional)')).toBeInTheDocument()
    expect(screen.getByText('Choose a CSV, XLSX, JSON or JSONL export')).toBeInTheDocument()
    expect(screen.getByText('Upload & discover')).toBeInTheDocument()
  })

  it('loads an existing project and lands on the Mapping step with discovered columns', async () => {
    getMock.mockResolvedValue(makeProject())

    renderWizard('/migration/7')

    await waitFor(() => expect(screen.getByText('PowerSchool 2026 export')).toBeInTheDocument())
    // Stepper shows all five steps with the mapping step active (label text).
    expect(screen.getByText('Field mapping')).toBeInTheDocument()
    expect(screen.getByText('Source')).toBeInTheDocument()
    expect(screen.getByText('Validate & Preview')).toBeInTheDocument()
    // Discovered columns render in the mapping table (unmapped until the
    // user confirms suggestions, so badges show the empty state).
    expect(screen.getByText('student_number')).toBeInTheDocument()
    expect(screen.getByText('full_name')).toBeInTheDocument()
    expect(screen.getAllByText('Unmapped').length).toBeGreaterThan(0)
  })

  it('renders an error state with a back action when the project fails to load', async () => {
    getMock.mockRejectedValue({ detail: 'Migration could not be loaded.' })

    renderWizard('/migration/999')

    await waitFor(() => expect(screen.getByText("Migration couldn't be loaded")).toBeInTheDocument())
    expect(screen.getByText('Back to migrations')).toBeInTheDocument()
  })

  it('shows the detected entity streams on the mapping step (Step 2)', async () => {
    getMock.mockResolvedValue(makeProject())

    renderWizard('/migration/7')

    await waitFor(() => expect(screen.getByText('Will import:')).toBeInTheDocument())
    expect(screen.getByText('Students')).toBeInTheDocument()
    expect(screen.getByText('Academic structure')).toBeInTheDocument()
    expect(screen.getByText('Attendance')).toBeInTheDocument()
    expect(screen.getByText('Fees / finance')).toBeInTheDocument()
  })

  it('shows validation issue categories and preview action badges', async () => {
    getMock.mockResolvedValue(
      makeProject({
        status: 'VALIDATING',
        validation: {
          blocking: 2,
          warnings: 1,
          info: 0,
          total: 12420,
          samples: [],
          categories: { duplicate: 1, invalid_date: 1, missing_optional: 1 },
          is_ready: false,
          validated_at: '2026-08-10T10:00:00Z',
        },
      })
    )
    previewMock.mockResolvedValue({
      total: 12420,
      limit: 5,
      rows: [
        {
          row: 1,
          before: { 'Student ID': 'S1001' },
          after: { student_number: 'S1001' },
          status: 'ok',
          action: 'CREATE',
          action_reason: 'A new record will be created',
        },
        {
          row: 2,
          before: { 'Student ID': 'S1002' },
          after: { student_number: 'S1002' },
          status: 'error',
          action: 'ERROR',
          action_reason: "Duplicate student number 'S1002'",
        },
      ],
      mapping: {},
    })

    renderWizard('/migration/7')

    await waitFor(() => expect(screen.getByText('Validate & preview')).toBeInTheDocument())
    // Category breakdown chips.
    expect(screen.getByText('duplicate · 1')).toBeInTheDocument()
    expect(screen.getByText('invalid date · 1')).toBeInTheDocument()
    // Preview rows carry CREATE / ERROR action badges (loaded async).
    await waitFor(() => expect(screen.getByText('CREATE')).toBeInTheDocument())
    expect(screen.getByText('ERROR')).toBeInTheDocument()
    expect(screen.getByText('A new record will be created')).toBeInTheDocument()
  })

  it('offers TXT / CSV / JSON report downloads on the reconcile step', async () => {
    getMock.mockResolvedValue(
      makeProject({
        status: 'COMPLETED',
        records_imported: 12420,
        reconciliation: {
          source_records: 12420,
          target_records: 12420,
          created: 12420,
          updated: 0,
          skipped: 0,
          rejected: 0,
          duplicates: 0,
          warnings: 0,
          run_id: 5,
          run_status: 'completed',
          entities: ['students'],
          reconciled_at: '2026-08-10T10:00:00Z',
        },
      })
    )

    renderWizard('/migration/7')

    await waitFor(() => expect(screen.getByText('Reconciliation & report')).toBeInTheDocument())
    expect(screen.getByText('TXT')).toBeInTheDocument()
    expect(screen.getByText('CSV')).toBeInTheDocument()
    expect(screen.getByText('JSON')).toBeInTheDocument()
    expect(screen.getByText('Roll back')).toBeInTheDocument()
  })
})
