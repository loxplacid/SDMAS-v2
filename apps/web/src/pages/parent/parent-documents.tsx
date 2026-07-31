import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { parentApi } from '../../api/parent/parent-api'
import type { LinkedChild, ParentDocument } from '../../api/parent/parent-api'
import { Loading, ErrorState, EmptyState, Card } from '../../components/ui'
import { useParentChildren } from '../../hooks/use-parent-children'
import { formatDate } from '../../lib/utils'

const TYPE_ICONS: Record<string, string> = {
  'application/pdf': 'M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z',
  'image/jpeg': 'M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z',
  'image/png': 'M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z',
  'application/msword': 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
}

const DEFAULT_ICON = 'M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z'

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function ParentDocumentsPage() {
  const navigate = useNavigate()
  const { linkedIds } = useParentChildren()
  const [children, setChildren] = useState<LinkedChild[]>([])
  const [selectedChildId, setSelectedChildId] = useState<number | null>(null)
  const [documents, setDocuments] = useState<ParentDocument[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (linkedIds.length === 0) { setLoading(false); return }
    parentApi.listChildren()
      .then((kids) => { setChildren(kids); if (kids.length > 0) setSelectedChildId(kids[0].id) })
      .catch((err: any) => setError(err?.detail || 'Failed to load children'))
      .finally(() => setLoading(false))
  }, [linkedIds])

  useEffect(() => {
    if (!selectedChildId) return
    setLoading(true)
    parentApi.getChildDocuments(selectedChildId)
      .then((res) => setDocuments(res.documents))
      .catch((err: any) => setError(err?.detail || 'Failed to load documents'))
      .finally(() => setLoading(false))
  }, [selectedChildId])

  if (loading) return <Loading text="Loading documents..." />
  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />
  if (children.length === 0) {
    return (
      <EmptyState
        title="No children linked"
        description="Link your children first to see their documents."
        action={{ label: 'Go to Dashboard', onClick: () => navigate('/parent') }}
      />
    )
  }

  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-24">
      {/* Mobile header */}
      <div className="sticky top-0 z-10 bg-[var(--color-surface)] border-b border-[var(--color-border)] px-4 py-3">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/parent')} className="flex items-center justify-center h-9 w-9 rounded-xl text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] transition-colors">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <h1 className="text-lg font-bold text-[var(--color-text-primary)]">Documents</h1>
            <p className="text-xs text-[var(--color-text-tertiary)]">Student files & records</p>
          </div>
        </div>
      </div>

      {/* Child tabs */}
      {children.length > 1 && (
        <div className="px-4 py-3 overflow-x-auto scrollbar-none">
          <div className="flex gap-2">
            {children.map((child) => (
              <button
                key={child.id}
                onClick={() => setSelectedChildId(child.id)}
                className={`shrink-0 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                  selectedChildId === child.id
                    ? 'bg-[var(--color-brand-accent)] text-white shadow-sm'
                    : 'bg-[var(--color-surface)] text-[var(--color-text-secondary)] border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]'
                }`}
              >
                {child.first_name} {child.last_name}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="px-4 py-4 space-y-3">
        {documents.length === 0 ? (
          <Card className="p-8 text-center">
            <div className="flex items-center justify-center h-12 w-12 rounded-2xl bg-[var(--color-surface-hover)] mx-auto mb-3">
              <svg className="h-6 w-6 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <p className="text-sm font-medium text-[var(--color-text-secondary)] mb-1">No documents yet</p>
            <p className="text-xs text-[var(--color-text-tertiary)]">Documents shared by the school will appear here</p>
          </Card>
        ) : (
          documents.map((doc) => (
            <Card key={doc.id} className="p-4">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center h-10 w-10 rounded-xl bg-[var(--color-surface-hover)] shrink-0">
                  <svg className="h-5 w-5 text-[var(--color-text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={TYPE_ICONS[doc.mime_type] || DEFAULT_ICON} />
                  </svg>
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-[var(--color-text-primary)] truncate">{doc.filename}</p>
                  <div className="flex items-center gap-2 text-xs text-[var(--color-text-tertiary)] mt-0.5">
                    <span>{formatFileSize(doc.file_size)}</span>
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

export default ParentDocumentsPage
