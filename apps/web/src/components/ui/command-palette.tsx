import { useState, useEffect, useRef, useCallback, useMemo, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { cn } from '../../lib/utils'
import { useMove, MOTION_DURATIONS, MOTION_EASINGS } from '../../lib/motion'

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

/**
 * One result row (spec §11.3.2): `Fade + 4px Slide N` — results settle from
 * above, matching the palette's Z arrival — staggered 20ms in reading order.
 * While an active query is filtering, the stagger collapses to 0 so new
 * results cross-fade fast instead of re-staggering (§11.3.4).
 */
function PaletteItem({
  item,
  index,
  selected,
  filtering,
  onSelect,
  onClick,
}: {
  item: CommandItem | SmartSearchResult
  index: number
  selected: boolean
  filtering: boolean
  onSelect: () => void
  onClick: () => void
}) {
  const { ref, style } = useMove(
    { verb: 'slide', direction: 'N', distance: 'D2', importance: 'I1' },
    { animateOnMount: true, staggerIndex: filtering ? 0 : index }
  )
  return (
    <div ref={ref} style={style}>
      <button
        data-command-item
        role="option"
        aria-selected={selected}
        className={cn(
          'relative flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-left transition-colors duration-100',
          selected
            ? 'text-[var(--color-brand-accent)]'
            : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]'
        )}
        onClick={onClick}
        onMouseEnter={onSelect}
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
    </div>
  )
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
  const accentRef = useRef<HTMLDivElement>(null)
  const closingRef = useRef(false)
  // Element that had focus when the palette opened — restored on close so
  // keyboard users land back where they left (P8 §18).
  const previousFocusRef = useRef<HTMLElement | null>(null)

  // Choreography (spec §6.10): backdrop `Fade` (base, 180ms) + panel
  // `Scale Z + Fade, D4, I3` (380ms) from center. Specs are memoized so the
  // resolved moves — and therefore `play` — stay referentially stable.
  const panelSpec = useMemo(
    () => ({ verb: 'scale', direction: 'Z', distance: 'D4', importance: 'I3' }) as const,
    []
  )
  const backdropSpec = useMemo(
    () => ({ verb: 'fade', distance: 'D2', importance: 'I2' }) as const,
    []
  )
  const panelMove = useMove(panelSpec, { animateOnMount: true })
  const backdropMove = useMove(backdropSpec, { animateOnMount: true })
  const panelRef = useRef<HTMLDivElement>(null)
  const backdropRef = useRef<HTMLDivElement>(null)

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
  const filtering = query.length > 0

  useEffect(() => {
    if (open) {
      setQuery('')
      setSelectedIndex(0)
      previousFocusRef.current =
        document.activeElement instanceof HTMLElement ? document.activeElement : null
      setTimeout(() => inputRef.current?.focus(), 50)
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [open])

  const handleClose = useCallback(() => {
    if (closingRef.current) return
    closingRef.current = true
    setClosing(true)
    const done = () => {
      closingRef.current = false
      setClosing(false)
      // Return focus to the summoning surface (P8 §18). The element may
      // have left the DOM while the palette was open — guard both.
      const previous = previousFocusRef.current
      if (previous && previous.isConnected && typeof previous.focus === 'function') {
        previous.focus()
      }
      onClose()
    }
    // Exit is the reverse of entry at 0.7× (spec §11.3.5): panel scales to
    // 0.98 + fades (220ms), backdrop fades (120ms). `onfinish` unmounts the
    // palette; under reduced tiers `play` applies instantly and completes
    // synchronously.
    panelMove.play(panelRef.current, 'exit', { onfinish: done })
    backdropMove.play(backdropRef.current, 'exit')
  }, [onClose, panelMove.play, backdropMove.play])

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
        handleClose()
        return
      }
    },
    [flatFiltered, selectedIndex, handleClose]
  )

  // Scroll selected item into view (guarded — jsdom lacks scrollIntoView)
  useEffect(() => {
    const item = listRef.current?.querySelectorAll<HTMLElement>('[data-command-item]')[selectedIndex]
    if (typeof item?.scrollIntoView === 'function') {
      item.scrollIntoView({ block: 'nearest' })
    }
  }, [selectedIndex])

  // Sliding selection accent (spec §11.3.3): the wash block moves between
  // rows at fast (120ms) via transform — the eye tracks the block, not the
  // text. A spatial move, so it is gated to the precise tier (§8).
  const accentTransition =
    panelMove.tier === 'precise'
      ? `transform ${MOTION_DURATIONS.fast}ms ${MOTION_EASINGS.standard}, height ${MOTION_DURATIONS.fast}ms ${MOTION_EASINGS.standard}`
      : 'none'

  useEffect(() => {
    const list = listRef.current
    const block = accentRef.current
    const items = list?.querySelectorAll<HTMLElement>('[data-command-item]')
    const item = items?.[selectedIndex]
    if (!list || !block || !item) {
      if (block) block.style.opacity = '0'
      return
    }
    block.style.opacity = '1'
    block.style.transform = `translateY(${item.offsetTop}px)`
    block.style.height = `${item.offsetHeight}px`
  }, [selectedIndex, displayGroups, accentTransition])

  // Global keyboard shortcut. This surface owns the *close* half of the
  // ⌘K toggle (AppLayout owns the open half): pressing ⌘K while open closes
  // the palette. Shift-modified ⌘K (⌘⇧K = universal search) is ignored so
  // the two bindings never fight (P8 §9).
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && !e.shiftKey && e.key === 'k') {
        e.preventDefault()
        if (open) handleClose()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, handleClose])

  if (!open && !closing) return null

  return (
    <div
      className="fixed inset-0 z-[var(--z-command)] flex items-start justify-center pt-[12vh]"
      onClick={(e) => { if (e.target === e.currentTarget) handleClose() }}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      <div
        ref={backdropRef}
        style={backdropMove.style}
        className="fixed inset-0 bg-black/40 backdrop-blur-sm"
        aria-hidden="true"
      />

      <div
        ref={panelRef}
        style={panelMove.style}
        className="relative w-full max-w-xl bg-[var(--color-surface)] rounded-2xl shadow-2xl border border-[var(--color-border)] overflow-hidden"
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
          className="relative max-h-[320px] overflow-y-auto px-2 py-2"
          role="listbox"
          aria-label="Commands"
        >
          {/* Sliding selection wash — positioned behind the rows */}
          <div
            ref={accentRef}
            aria-hidden="true"
            className="absolute left-2 right-2 rounded-lg bg-[var(--color-brand-accent-subtle)] pointer-events-none"
            style={{ top: 0, opacity: 0, transition: accentTransition }}
          />
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
                    return (
                      <PaletteItem
                        key={item.id}
                        item={item}
                        index={idx}
                        selected={idx === selectedIndex}
                        filtering={filtering}
                        onSelect={() => setSelectedIndex(idx)}
                        onClick={() => { item.action(); handleClose() }}
                      />
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
