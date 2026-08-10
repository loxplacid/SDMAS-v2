import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

interface ShortcutKeyProps {
  children: ReactNode
  /** Button tone = chip on a solid primary button; muted = chip on a surface. */
  tone?: 'button' | 'muted'
  className?: string
}

/**
 * Shortcut key hint rendered inside a <kbd>. Consolidates the identical chip
 * markup previously copy-pasted across list pages' primary action buttons.
 */
export function ShortcutKey({ children, tone = 'button', className }: ShortcutKeyProps) {
  return (
    <kbd
      className={cn(
        'ml-2 hidden sm:inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium',
        tone === 'button' ? 'bg-white/20 text-white/80' : 'bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]',
        className
      )}
    >
      {children}
    </kbd>
  )
}
