import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { studentPortalApi } from '../../api/student/student-portal-api'
import type { StudentDocument } from '../../api/student/student-portal-api'
import { Loading, ErrorState, EmptyState, Card } from '../../components/ui'
import { formatDate } from '../../lib/utils'

const FILE_ICONS: Record<string, string> = {
  'application/pdf': 'M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z',
  'image/': 'M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z',
}

function getIcon(mimeType: string): string {
  for (const [prefix, icon] of Object.entries(FILE_ICONS)) {
    if (mimeType.startsWith(prefix)) return icon
  }
  return 'M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z'
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function StudentDocumentsPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<{ documents: StudentDocument[] } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    studentPortalApi.getDocuments()
      .then(setData)
      .catch((err: any) => setError(err?.detail || 'Failed to load documents'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Loading text="Loading documents..." />
  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />

  const documents = data?.documents || []

  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-24">
      <div className="sticky top-0 z-10 bg-[var(--color-surface)] border-b border-[var(--color-border)] px-4 py-3">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/student')} className="flex items-center justify-center h-9 w-9 rounded-xl text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] transition-colors">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
          </button>
          <div><h1 className="text-lg font-bold text-[var(--color-text-primary)]">My Documents</h1></div>
        </div>
      </div>

      <div className="px-4 py-4 space-y-3">
        {documents.length === 0 ? (
          <Card className="p-8 text-center">
            <div className="flex items-center justify-center h-12 w-12 rounded-2xl bg-[var(--color-surface-hover)] mx-auto mb-3">
              <svg className="h-6 w-6 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <p className="text-sm text-[var(--color-text-tertiary)]">No documents uploaded yet</p>
          </Card>
        ) : (
          documents.map((doc) => (
            <Card key={doc.id} className="p-4">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center h-10 w-10 rounded-xl bg-[var(--color-surface-hover)] shrink-0">
                  <svg className="h-5 w-5 text-[var(--color-text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={getIcon(doc.mime_type)} />
                  </svg>
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-[var(--color-text-primary)] truncate">{doc.filename}</p>
                  <div className="flex items-center gap-2 text-xs text-[var(--color-text-tertiary)] mt-0.5">
                    <span>{formatSize(doc.file_size)}</span>
                    <span>&middot;</span>
                    <span>{formatDate(doc.created_at)}</span>
                    {doc.category_name && (
                      <>
                        <span>&middot;</span>
                        <span className="px-1.5 py-0.5 rounded bg-[var(--color-surface-hover)]">{doc.category_name}</span>
                      </>
                    )}
                  </div>
                </div>
                <svg className="h-4 w-4 text-[var(--color-text-tertiary)] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  )
}

export default StudentDocumentsPage
