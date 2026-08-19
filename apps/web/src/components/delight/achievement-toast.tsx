import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { useMove } from '../../lib/motion'
import { cn } from '../../lib/utils'

/**
 * Glint §5.2 — the L4 achievement toast.
 *
 * The milestone moment: drawn checkmark → label → caption → one soft burst
 * (a radial glow at the checkmark, 150ms after entry — the quiet-first
 * rule). Own `role="status"` region so a save (L2) followed by a milestone
 * (L4) produces one polite announcement, never two. Auto-dismisses at 5s
 * (the milestone earns an extra beat over the standard toast's 4s). One at
 * a time — the provider replaces, never stacks.
 */
export interface AchievementToastProps {
  label: string
  caption: string
  onDismiss: () => void
}

export function AchievementToast({ label, caption, onDismiss }: AchievementToastProps) {
  const { ref, style, play } = useMove(
    { verb: 'slide', direction: 'SE', distance: 'D3', importance: 'I3' },
    { animateOnMount: true }
  )
  const itemRef = useRef<HTMLDivElement>(null)
  const exitPlayedRef = useRef(false)
  const [leaving, setLeaving] = useState(false)

  // The milestone earns an extra beat: 5s vs the standard toast's 4s.
  useEffect(() => {
    const t = window.setTimeout(() => setLeaving(true), 5000)
    return () => window.clearTimeout(t)
  }, [])

  useEffect(() => {
    if (!leaving || exitPlayedRef.current) return
    exitPlayedRef.current = true
    play(itemRef.current, 'exit', { onfinish: onDismiss })
  }, [leaving, play, onDismiss])

  const setItemRef = (el: HTMLDivElement | null) => {
    itemRef.current = el
    ref(el)
  }

  return (
    <div
      ref={setItemRef}
      style={style as CSSProperties}
      role="status"
      className={cn(
        'pointer-events-auto relative flex items-center gap-4 overflow-hidden rounded-xl',
        'bg-[var(--color-surface)] border border-[var(--color-border)] shadow-xl',
        'pl-4 pr-4 py-3.5'
      )}
    >
      {/* The soft burst — one shot, no particles, behind the mark. */}
      <span
        aria-hidden="true"
        className="animate-milestone-burst absolute left-5 top-1/2 -translate-y-1/2 h-6 w-6 rounded-full bg-[var(--color-brand-accent)]/20"
      />
      {/* Drawn checkmark (same grammar as the L2 success check). */}
      <span className="relative flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-[var(--color-brand-accent-subtle)]">
        <svg className="h-3.5 w-3.5 text-[var(--color-brand-accent)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2.5}>
          <path
            className="animate-draw-check"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray={24}
            strokeDashoffset={24}
            d="M5 13l4 4L19 7"
          />
        </svg>
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-[var(--color-text-primary)] leading-snug">{label}</p>
        <p className="text-xs text-[var(--color-text-secondary)] mt-0.5 leading-snug">{caption}</p>
      </div>
      <button
        onClick={() => setLeaving(true)}
        className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-lg text-[var(--color-text-tertiary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] motion-safe:transition-colors"
        aria-label="Dismiss"
      >
        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}
