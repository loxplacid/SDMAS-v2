import { useState, useEffect, useCallback, useRef } from 'react'
import { studentApi } from '../../api/student/student-api'
import type { StudentResponse } from '../../api/generated/types'
import { Input } from './input'
import { Button } from './button'
import { cn } from '../../lib/utils'

interface LinkChildDialogProps {
  open: boolean
  onClose: () => void
  linkedIds: number[]
  onLink: (studentId: number) => void
  onLinkMultiple: (studentIds: number[]) => void
}

export function LinkChildDialog({ open, onClose, linkedIds, onLink, onLinkMultiple }: LinkChildDialogProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<StudentResponse[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const inputRef = useRef<HTMLInputElement>(null)

  // Focus input when dialog opens
  useEffect(() => {
    if (open) {
      setQuery('')
      setResults([])
      setSelectedIds(new Set())
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [open])

  // Search students as user types
  useEffect(() => {
    if (!query.trim()) {
      setResults([])
      return
    }
    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const result = await studentApi.list({ search: query.trim(), size: 20 })
        setResults(result.items)
      } catch {
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [query])

  const toggleSelect = useCallback((id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  const handleLinkSelected = useCallback(() => {
    if (selectedIds.size > 0) {
      onLinkMultiple(Array.from(selectedIds))
      onClose()
    }
  }, [selectedIds, onLinkMultiple, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <div className="fixed inset-0 bg-black/40 animate-fade-in" onClick={onClose} />
      <div className="relative bg-[var(--color-surface)] rounded-2xl shadow-xl border border-[var(--color-border)] w-full max-w-lg max-h-[80vh] flex flex-col animate-fade-in-up">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)]">
          <div>
            <h2 className="text-base font-semibold text-[var(--color-text-primary)]">Link a Child</h2>
            <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">Search for a student to add to your parent view</p>
          </div>
          <button
            onClick={onClose}
            className="flex items-center justify-center h-8 w-8 rounded-lg text-[var(--color-text-tertiary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] transition-colors"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Search */}
        <div className="px-6 py-4 border-b border-[var(--color-border)]">
          <Input
            ref={inputRef}
            placeholder="Search by name or student number..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto px-6 py-3 space-y-1 min-h-[200px]">
          {!query.trim() ? (
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <div className="flex items-center justify-center h-10 w-10 rounded-xl bg-[var(--color-surface-hover)] mb-3">
                <svg className="h-5 w-5 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <p className="text-sm text-[var(--color-text-tertiary)]">Type a name or student number to search</p>
            </div>
          ) : loading ? (
            <div className="space-y-2 py-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-14 rounded-xl bg-[var(--color-border)] animate-skeleton" />
              ))}
            </div>
          ) : results.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <p className="text-sm font-medium text-[var(--color-text-secondary)]">No students found</p>
              <p className="text-xs text-[var(--color-text-tertiary)] mt-1">Try a different search term</p>
            </div>
          ) : (
            results.map((student) => {
              const alreadyLinked = linkedIds.includes(student.id)
              const isSelected = selectedIds.has(student.id)
              return (
                <button
                  key={student.id}
                  onClick={() => {
                    if (alreadyLinked) return
                    toggleSelect(student.id)
                  }}
                  disabled={alreadyLinked}
                  className={cn(
                    'w-full flex items-center gap-3 p-3 rounded-xl text-left transition-all duration-[var(--motion-fast)]',
                    alreadyLinked
                      ? 'opacity-50 cursor-not-allowed'
                      : isSelected
                        ? 'bg-[var(--color-brand-accent)]/10 border border-[var(--color-brand-accent)]/20'
                        : 'hover:bg-[var(--color-surface-hover)] border border-transparent',
                  )}
                >
                  {/* Checkbox */}
                  <div className={cn(
                    'flex items-center justify-center h-5 w-5 rounded border-2 transition-colors flex-shrink-0',
                    alreadyLinked
                      ? 'border-[var(--color-success)] bg-[var(--color-success)]/10'
                      : isSelected
                        ? 'border-[var(--color-brand-accent)] bg-[var(--color-brand-accent)]'
                        : 'border-[var(--color-border)]',
                  )}>
                    {(alreadyLinked || isSelected) && (
                      <svg className="h-3 w-3 text-white" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" />
                      </svg>
                    )}
                  </div>
                  {/* Avatar */}
                  <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-[var(--color-brand-accent)]/10 flex-shrink-0">
                    <span className="text-sm font-bold text-[var(--color-brand-accent)]">
                      {student.first_name.charAt(0)}{student.last_name.charAt(0)}
                    </span>
                  </div>
                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-[var(--color-text-primary)] truncate">
                      {student.first_name} {student.last_name}
                    </p>
                    <p className="text-xs text-[var(--color-text-tertiary)] truncate">
                      {student.student_number}
                      {alreadyLinked && <span className="ml-2 text-[var(--color-success)]">Already linked</span>}
                    </p>
                  </div>
                </button>
              )
            })
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-[var(--color-border)]">
          <p className="text-xs text-[var(--color-text-tertiary)]">
            {selectedIds.size > 0
              ? `${selectedIds.size} student${selectedIds.size !== 1 ? 's' : ''} selected`
              : 'Select students to link'}
          </p>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={onClose}>Cancel</Button>
            <Button onClick={handleLinkSelected} disabled={selectedIds.size === 0}>
              Link {selectedIds.size > 0 ? `(${selectedIds.size})` : ''}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
