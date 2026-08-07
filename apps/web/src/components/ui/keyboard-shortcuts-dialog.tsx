import { useEffect, useRef, useState, useCallback } from 'react'
import { cn } from '../../lib/utils'

interface ShortcutEntry {
  keys: string[]
  label: string
  description: string
}

interface ShortcutGroup {
  label: string
  shortcuts: ShortcutEntry[]
}

const SHORTCUT_GROUPS: ShortcutGroup[] = [
  {
    label: 'Global',
    shortcuts: [
      { keys: ['⌘K'], label: 'Universal Search', description: 'Search everything — students, invoices, classes, attendance (works offline via the local index)' },
      { keys: ['⌘⇧K'], label: 'Universal Search', description: 'Same as ⌘K — search across all entities instantly' },
      { keys: ['?'], label: 'Keyboard Shortcuts', description: 'Show this help dialog' },
    ],
  },
  {
    label: 'Navigation',
    shortcuts: [
      { keys: ['⌘B'], label: 'Toggle Sidebar', description: 'Show/hide mobile navigation' },
      { keys: ['⌘', '↑', '↓'], label: 'Navigate Results', description: 'Move through command palette results' },
      { keys: ['↵'], label: 'Select', description: 'Activate focused command palette item' },
      { keys: ['Esc'], label: 'Close', description: 'Close modals, dropdowns, and the command palette' },
    ],
  },
  {
    label: 'List Pages',
    shortcuts: [
      { keys: ['/'], label: 'Focus Search', description: 'Jump to the search or filter input' },
      { keys: ['N'], label: 'Add New', description: 'Open the create modal for the current page' },
    ],
  },
  {
    label: 'Forms',
    shortcuts: [
      { keys: ['⌘S'], label: 'Save', description: 'Submit the current form (when focused on a form)' },
      { keys: ['Esc'], label: 'Cancel', description: 'Close the form or modal without saving' },
    ],
  },
]

function ShortcutKey({ keys }: { keys: string[] }) {
  return (
    <span className="inline-flex items-center gap-0.5">
      {keys.map((key, i) => (
        <span key={i}>
          {i > 0 && <span className="mx-0.5 text-[var(--color-text-muted)]">+</span>}
          <kbd className="inline-flex items-center justify-center min-w-[22px] h-5 px-1 rounded text-[10px] font-semibold font-mono bg-[var(--color-bg)] text-[var(--color-text-secondary)] border border-[var(--color-border)] leading-none">
            {key}
          </kbd>
        </span>
      ))}
    </span>
  )
}

interface KeyboardShortcutsDialogProps {
  open: boolean
  onClose: () => void
}

export function KeyboardShortcutsDialog({ open, onClose }: KeyboardShortcutsDialogProps) {
  const [closing, setClosing] = useState(false)
  const dialogRef = useRef<HTMLDivElement>(null)

  const handleClose = useCallback(() => {
    setClosing(true)
    setTimeout(() => {
      setClosing(false)
      onClose()
    }, 120)
  }, [onClose])

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        handleClose()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, handleClose])

  // Focus trap
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden'
      dialogRef.current?.focus()
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [open])

  if (!open && !closing) return null
  const show = open && !closing

  return (
    <div
      className={cn(
        'fixed inset-0 z-[200] flex items-center justify-center p-4',
        show ? 'animate-fade-in' : 'animate-fade-out'
      )}
      onClick={(e) => { if (e.target === e.currentTarget) handleClose() }}
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
    >
      <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" aria-hidden="true" />

      <div
        ref={dialogRef}
        tabIndex={-1}
        className={cn(
          'relative w-full max-w-lg bg-[var(--color-surface)] rounded-2xl shadow-2xl border border-[var(--color-border)] overflow-hidden outline-none',
          show ? 'animate-fade-in-scale' : 'animate-fade-out-scale'
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)]">
          <div>
            <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">Keyboard Shortcuts</h2>
            <p className="text-sm text-[var(--color-text-tertiary)] mt-0.5">
              {SHORTCUT_GROUPS.reduce((sum, g) => sum + g.shortcuts.length, 0)} shortcuts available
            </p>
          </div>
          <button
            onClick={handleClose}
            className="flex items-center justify-center h-7 w-7 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-hover)] transition-colors"
            aria-label="Close"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Shortcut groups */}
        <div className="max-h-[60vh] overflow-y-auto px-2 py-2">
          {SHORTCUT_GROUPS.map((group) => (
            <div key={group.label}>
              <p className="px-4 pt-3 pb-1.5 text-[10px] font-semibold uppercase tracking-widest text-[var(--color-text-muted)]">
                {group.label}
              </p>
              {group.shortcuts.map((shortcut) => (
                <div
                  key={shortcut.label}
                  className="flex items-center justify-between px-4 py-2 rounded-lg hover:bg-[var(--color-surface-hover)] transition-colors"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-[var(--color-text-primary)] truncate">
                      {shortcut.label}
                    </p>
                    <p className="text-xs text-[var(--color-text-tertiary)] truncate">
                      {shortcut.description}
                    </p>
                  </div>
                  <ShortcutKey keys={shortcut.keys} />
                </div>
              ))}
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-[var(--color-border)] bg-[var(--color-bg)]">
          <p className="text-xs text-[var(--color-text-muted)]">
            Press <kbd className="inline-flex items-center px-1 h-4 rounded text-[10px] font-medium bg-[var(--color-surface)] border border-[var(--color-border)]">?</kbd> at any time to open this dialog
          </p>
        </div>
      </div>
    </div>
  )
}
