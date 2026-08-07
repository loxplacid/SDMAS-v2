import { useState, useEffect, useRef, useCallback } from 'react'
import { cn } from '../../lib/utils'
import { recordOpen } from '../../lib/search/ranking'
import type {
  UniversalSearchResult,
  UniversalSearchStatus,
} from '../../hooks/use-universal-search'
import type { SearchEntityType } from '../../api/search/search-api'

export type UniversalEntityTab = SearchEntityType | '__all__'

const ENTITY_TABS: { type: UniversalEntityTab; label: string }[] = [
  { type: '__all__', label: 'All' },
  { type: 'student', label: 'Students' },
  { type: 'teacher', label: 'Teachers' },
  { type: 'class', label: 'Classes' },
  { type: 'section', label: 'Sections' },
  { type: 'subject', label: 'Subjects' },
  { type: 'fee', label: 'Fees' },
  { type: 'payment', label: 'Payments' },
  { type: 'receipt', label: 'Receipts' },
  { type: 'attendance', label: 'Attendance' },
  { type: 'grade_record', label: 'Exam Marks' },
  { type: 'document', label: 'Documents' },
  { type: 'notification', label: 'Notifications' },
  { type: 'leave_request', label: 'Leave' },
  { type: 'admission_application', label: 'Admissions' },
]

interface UniversalSearchModalProps {
  open: boolean
  onClose: () => void
  search: (q: string) => Promise<UniversalSearchResult>
  status: UniversalSearchStatus
  onNavigate: (route: string, id: string) => void
}

export function UniversalSearchModal({
  open,
  onClose,
  search,
  status,
  onNavigate,
}: UniversalSearchModalProps) {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<UniversalSearchResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<UniversalEntityTab>('__all__')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [closing, setClosing] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const seqRef = useRef(0)

  const hasQuery = query.trim().length > 0
  const flatResults = result?.results ?? []
  const visibleGrouped = hasQuery
    ? activeTab === '__all__'
      ? result?.grouped ?? []
      : (result?.grouped ?? []).filter((g) => g.entity_type === activeTab)
    : []

  const runSearch = useCallback(
    async (q: string) => {
      const seq = ++seqRef.current
      setLoading(true)
      try {
        const res = await search(q)
        if (seq === seqRef.current) setResult(res)
      } finally {
        if (seq === seqRef.current) setLoading(false)
      }
    },
    [search],
  )

  useEffect(() => {
    if (!open) return
    setQuery('')
    setResult(null)
    setActiveTab('__all__')
    setSelectedIndex(0)
    const t = setTimeout(() => inputRef.current?.focus(), 50)
    document.body.style.overflow = 'hidden'
    return () => {
      clearTimeout(t)
      document.body.style.overflow = ''
    }
  }, [open])

  useEffect(() => {
    if (open) void runSearch(query)
  }, [query, runSearch, open])

  const handleClose = useCallback(() => {
    setClosing(true)
    setTimeout(() => {
      setClosing(false)
      onClose()
    }, 120)
  }, [onClose])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        handleClose()
        return
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex((i) => Math.min(i + 1, Math.max(flatResults.length - 1, 0)))
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex((i) => Math.max(i - 1, 0))
        return
      }
      if (e.key === 'Enter' && flatResults[selectedIndex]) {
        e.preventDefault()
        const item = flatResults[selectedIndex]
        recordOpen(item.id)
        onNavigate(item.route, item.id)
        return
      }
      if (e.key === 'Tab') {
        e.preventDefault()
        const tabs = ENTITY_TABS
        const currentIdx = tabs.findIndex((t) => t.type === activeTab)
        const nextIdx = e.shiftKey
          ? (currentIdx - 1 + tabs.length) % tabs.length
          : (currentIdx + 1) % tabs.length
        setActiveTab(tabs[nextIdx].type)
      }
    },
    [flatResults, selectedIndex, handleClose, onNavigate, activeTab],
  )

  useEffect(() => {
    setSelectedIndex(0)
  }, [query, activeTab])

  useEffect(() => {
    if (listRef.current) {
      const items = listRef.current.querySelectorAll('[data-result-item]')
      items[selectedIndex]?.scrollIntoView({ block: 'nearest' })
    }
  }, [selectedIndex])

  if (!open && !closing) return null
  const show = open && !closing

  return (
    <div
      className={cn(
        'fixed inset-0 z-[200] flex items-start justify-center pt-[8vh]',
        show ? 'animate-fade-in' : 'animate-fade-out',
      )}
      onClick={(e) => {
        if (e.target === e.currentTarget) handleClose()
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Universal search"
    >
      <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" aria-hidden="true" />

      <div
        className={cn(
          'relative w-full max-w-2xl bg-[var(--color-surface)] rounded-2xl shadow-2xl border border-[var(--color-border)] overflow-hidden',
          show ? 'animate-fade-in-scale' : 'animate-fade-out-scale',
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-[var(--color-border)]">
          {loading ? (
            <svg className="h-5 w-5 text-[var(--color-brand-accent)] animate-spin flex-shrink-0" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            <svg className="h-5 w-5 text-[var(--color-text-muted)] flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          )}
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setSelectedIndex(0)
            }}
            onKeyDown={handleKeyDown}
            placeholder="Search everything — students, invoices, classes, attendance…"
            className="flex-1 bg-transparent border-none outline-none text-base text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)]"
            autoComplete="off"
            spellCheck={false}
          />
          {result && hasQuery && !loading && (
            <span className="text-[10px] text-[var(--color-text-muted)] whitespace-nowrap">
              {result.total} results in {Math.round(result.tookMs)}ms
            </span>
          )}
          <kbd className="hidden sm:inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium bg-[var(--color-bg)] text-[var(--color-text-muted)] border border-[var(--color-border)]">
            <span>ESC</span>
          </kbd>
        </div>

        {/* Entity Type Tabs */}
        {hasQuery && (
          <div className="flex items-center gap-1 px-3 py-2 border-b border-[var(--color-border)] overflow-x-auto">
            {ENTITY_TABS.map((tab) => {
              const isActive = activeTab === tab.type
              return (
                <button
                  key={tab.type}
                  onClick={() => setActiveTab(tab.type)}
                  className={cn(
                    'px-2.5 py-1 rounded-lg text-xs font-medium whitespace-nowrap transition-colors',
                    isActive
                      ? 'bg-[var(--color-brand-accent-subtle)] text-[var(--color-brand-accent)]'
                      : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]',
                  )}
                >
                  {tab.label}
                </button>
              )
            })}
          </div>
        )}

        {/* Results */}
        <div
          ref={listRef}
          className="max-h-[400px] overflow-y-auto px-2 py-2"
          role="listbox"
          aria-label="Search results"
        >
          {hasQuery && visibleGrouped.length === 0 && !loading && (
            <div className="flex flex-col items-center py-10 text-center">
              <svg className="h-8 w-8 text-[var(--color-text-muted)] mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <p className="text-sm text-[var(--color-text-muted)]">No results found for "{query}"</p>
              <p className="text-xs text-[var(--color-text-tertiary)] mt-1">Try different keywords or check spelling</p>
            </div>
          )}

          {loading && hasQuery && (
            <div className="flex items-center justify-center py-10">
              <div className="flex flex-col items-center gap-2">
                <div className="h-6 w-6 rounded-full border-2 border-[var(--color-brand-accent)] border-t-transparent animate-spin" />
                <p className="text-xs text-[var(--color-text-muted)]">Searching…</p>
              </div>
            </div>
          )}

          {visibleGrouped.map((group) => (
            <div key={group.entity_type}>
              <div className="flex items-center gap-2 px-3 py-2">
                {group.icon && (
                  <svg className="h-3.5 w-3.5 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={group.icon} />
                  </svg>
                )}
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--color-text-muted)]">
                  {group.label}
                </p>
                <span className="text-[10px] text-[var(--color-text-tertiary)]">
                  ({group.items.length})
                </span>
              </div>
              {group.items.map((item, ii) => {
                const globalIdx =
                  visibleGrouped.slice(0, visibleGrouped.indexOf(group)).reduce((acc, g) => acc + g.items.length, 0) + ii
                const isSelected = globalIdx === selectedIndex
                return (
                  <button
                    key={item.id}
                    data-result-item
                    role="option"
                    aria-selected={isSelected}
                    className={cn(
                      'flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-left transition-all duration-100',
                      isSelected
                        ? 'bg-[var(--color-brand-accent-subtle)] text-[var(--color-brand-accent)]'
                        : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]',
                    )}
                    onClick={() => {
                      recordOpen(item.id)
                      onNavigate(item.route, item.id)
                    }}
                    onMouseEnter={() => setSelectedIndex(globalIdx)}
                  >
                    {group.icon && (
                      <svg className="h-4.5 w-4.5 flex-shrink-0 opacity-70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={group.icon} />
                      </svg>
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium truncate">{item.label}</p>
                      {item.description && (
                        <p className="text-xs text-[var(--color-text-tertiary)] truncate">{item.description}</p>
                      )}
                    </div>
                    {item.score != null && item.score > 0 && (
                      <span className="text-[10px] text-[var(--color-text-muted)] bg-[var(--color-bg)] px-1.5 py-0.5 rounded flex-shrink-0">
                        {Math.round(item.score * 100)}%
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          ))}

          {!hasQuery && (
            <div className="flex flex-col items-center py-10 text-center">
              <svg className="h-10 w-10 text-[var(--color-text-muted)] mb-3 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <p className="text-sm text-[var(--color-text-muted)]">Type to search everything</p>
              <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
                Students, teachers, classes, fees, receipts, attendance, exam marks…
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-4 px-5 py-2.5 border-t border-[var(--color-border)] bg-[var(--color-bg)]">
          <div className="flex items-center gap-1.5 text-[11px] text-[var(--color-text-muted)]">
            <kbd className="inline-flex items-center justify-center h-4.5 w-4.5 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[10px] font-medium">↑</kbd>
            <kbd className="inline-flex items-center justify-center h-4.5 w-4.5 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[10px] font-medium">↓</kbd>
            <span>navigate</span>
          </div>
          <div className="flex items-center gap-1.5 text-[11px] text-[var(--color-text-muted)]">
            <kbd className="inline-flex items-center px-1.5 h-4.5 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[10px] font-medium">↵</kbd>
            <span>select</span>
          </div>
          <div className="flex items-center gap-1.5 text-[11px] text-[var(--color-text-muted)]">
            <kbd className="inline-flex items-center px-1.5 h-4.5 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[10px] font-medium">esc</kbd>
            <span>close</span>
          </div>
          <div className="ml-auto flex items-center gap-1.5 text-[11px] text-[var(--color-text-muted)]">
            {status.error ? (
              <span className="text-[var(--color-danger)]">Index sync failed</span>
            ) : status.inProgress ? (
              <span className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-brand-accent)] animate-pulse" />
                Syncing…
              </span>
            ) : status.lastSyncedAt ? (
              <span className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-success)]" />
                Index up to date
              </span>
            ) : (
              <span className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-text-tertiary)]" />
                Warming index…
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
