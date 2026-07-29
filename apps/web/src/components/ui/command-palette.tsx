import { useState, useEffect, useRef, useCallback, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { cn } from '../../lib/utils'

interface CommandItem {
  id: string
  label: string
  description?: string
  icon?: string
  action: () => void
  keywords?: string[]
}

interface CommandGroup {
  label: string
  items: CommandItem[]
}

interface SmartSearchResult {
  id: string
  label: string
  description: string
  type: string
  icon: string
  action: () => void
  keywords: string[]
}

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
  groups: CommandGroup[]
  smartSearch?: (query: string) => SmartSearchResult[]
  searchLoaded?: boolean
  placeholder?: string
  emptyMessage?: string
}

export function CommandPalette({
  open,
  onClose,
  groups,
  smartSearch,
  searchLoaded = false,
  placeholder = 'Search pages and actions...',
  emptyMessage = 'No results found.',
}: CommandPaletteProps) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [closing, setClosing] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const smartResults = smartSearch ? smartSearch(query) : []

  const filteredGroups = groups
    .map((g) => ({
      ...g,
      items: g.items.filter(
        (item) =>
          !query ||
          item.label.toLowerCase().includes(query.toLowerCase()) ||
          item.keywords?.some((k) => k.toLowerCase().includes(query.toLowerCase()))
      ),
    }))
    .filter((g) => g.items.length > 0)

  // Build display groups: smart results first (if query is active), then nav groups
  const displayGroups = query && smartResults.length > 0
    ? [{ label: 'Search Results', items: smartResults }, ...filteredGroups]
    : filteredGroups

  const flatFiltered = displayGroups.flatMap((g) => g.items)

  useEffect(() => {
    if (open) {
      setQuery('')
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 50)
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [open])

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
        setSelectedIndex((i) => Math.min(i + 1, flatFiltered.length - 1))
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex((i) => Math.max(i - 1, 0))
        return
      }
      if (e.key === 'Enter' && flatFiltered[selectedIndex]) {
        e.preventDefault()
        flatFiltered[selectedIndex].action()
        onClose()
        return
      }
    },
    [flatFiltered, selectedIndex, onClose, handleClose]
  )

  // Scroll selected item into view
  useEffect(() => {
    if (listRef.current) {
      const items = listRef.current.querySelectorAll('[data-command-item]')
      items[selectedIndex]?.scrollIntoView({ block: 'nearest' })
    }
  }, [selectedIndex])

  // Global keyboard shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        if (open) handleClose()
        else {
          // We need a way to open - parent controls this
        }
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, handleClose])

  if (!open && !closing) return null

  const show = open && !closing

  return (
    <div
      className={cn(
        'fixed inset-0 z-[200] flex items-start justify-center pt-[12vh]',
        show ? 'animate-fade-in' : 'animate-fade-out'
      )}
      onClick={(e) => { if (e.target === e.currentTarget) handleClose() }}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" aria-hidden="true" />

      <div
        className={cn(
          'relative w-full max-w-xl bg-[var(--color-surface)] rounded-2xl shadow-2xl border border-[var(--color-border)] overflow-hidden',
          show ? 'animate-fade-in-scale' : 'animate-fade-out-scale'
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-[var(--color-border)]">
          <svg className="h-5 w-5 text-[var(--color-text-muted)] flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setSelectedIndex(0) }}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className="flex-1 bg-transparent border-none outline-none text-base text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)]"
            autoComplete="off"
            spellCheck={false}
          />
          <kbd className="hidden sm:inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium bg-[var(--color-bg)] text-[var(--color-text-muted)] border border-[var(--color-border)]">
            <span>ESC</span>
          </kbd>
        </div>

        {/* Results */}
        <div
          ref={listRef}
          className="max-h-[320px] overflow-y-auto px-2 py-2"
          role="listbox"
          aria-label="Commands"
        >
          {displayGroups.length === 0 ? (
            <div className="flex flex-col items-center py-8 text-center">
              <svg className="h-8 w-8 text-[var(--color-text-muted)] mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              {!searchLoaded && query ? (
                <p className="text-sm text-[var(--color-text-muted)]">Loading search index...</p>
              ) : (
                <p className="text-sm text-[var(--color-text-muted)]">{emptyMessage}</p>
              )}
            </div>
          ) : (
            displayGroups.map((group, gi) => {
              let globalIndex = 0
              // Calculate starting index for this group
              for (let g = 0; g < gi; g++) {
                globalIndex += displayGroups[g].items.length
              }

              return (
                <div key={group.label}>
                  <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-widest text-[var(--color-text-muted)]">
                    {group.label}
                  </p>
                  {group.items.map((item, ii) => {
                    const idx = globalIndex + ii
                    const isSelected = idx === selectedIndex
                    return (
                      <button
                        key={item.id}
                        data-command-item
                        role="option"
                        aria-selected={isSelected}
                        className={cn(
                          'flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-left transition-all duration-100',
                          isSelected
                            ? 'bg-[var(--color-brand-accent-subtle)] text-[var(--color-brand-accent)]'
                            : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]'
                        )}
                        onClick={() => { item.action(); handleClose() }}
                        onMouseEnter={() => setSelectedIndex(idx)}
                      >
                        {item.icon && (
                          <svg className="h-4.5 w-4.5 flex-shrink-0 opacity-70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={item.icon} />
                          </svg>
                        )}
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium truncate">{item.label}</p>
                          {item.description && (
                            <p className="text-xs text-[var(--color-text-tertiary)] truncate">{item.description}</p>
                          )}
                        </div>
                      </button>
                    )
                  })}
                </div>
              )
            })
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
            <kbd className="inline-flex items-center justify-center h-4.5 w-4.5 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[10px] font-medium">?</kbd>
            <span>shortcuts</span>
          </div>
        </div>
      </div>
    </div>
  )
}

// Hook to manage command palette state
export function useCommandPalette(groups: CommandGroup[]) {
  const [open, setOpen] = useState(false)

  const toggle = useCallback(() => setOpen((o) => !o), [])
  const openPalette = useCallback(() => setOpen(true), [])
  const closePalette = useCallback(() => setOpen(false), [])

  // Global keyboard shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setOpen((prev) => !prev)
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  return {
    open,
    toggle,
    openPalette,
    closePalette,
    commandPalette: (
      <CommandPalette
        open={open}
        onClose={closePalette}
        groups={groups}
      />
    ),
  }
}
