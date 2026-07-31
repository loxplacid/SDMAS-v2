import {
  useState,
  useRef,
  useEffect,
  type ReactNode,
  type KeyboardEvent,
  useCallback,
} from 'react'
import { cn } from '../../lib/utils'

// ── Types ────────────────────────────────────────────────────────────

type DropdownPosition = 'bottom-left' | 'bottom-right' | 'top-left' | 'top-right'

export interface DropdownItem {
  id: string
  label: string
  icon?: ReactNode
  shortcut?: string
  disabled?: boolean
  danger?: boolean
  divider?: boolean
  onClick?: () => void
}

interface DropdownMenuProps {
  trigger: ReactNode
  items: DropdownItem[]
  position?: DropdownPosition
  className?: string
  menuClassName?: string
  disabled?: boolean
  header?: ReactNode
}

// ── Position Classes ────────────────────────────────────────────────

const positionClasses: Record<DropdownPosition, string> = {
  'bottom-left': 'top-full left-0 mt-1.5',
  'bottom-right': 'top-full right-0 mt-1.5',
  'top-left': 'bottom-full left-0 mb-1.5',
  'top-right': 'bottom-full right-0 mb-1.5',
}

// ── Component ───────────────────────────────────────────────────────

export function DropdownMenu({
  trigger,
  items,
  position = 'bottom-left',
  className,
  menuClassName,
  disabled = false,
  header,
}: DropdownMenuProps) {
  const [open, setOpen] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [closing, setClosing] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const menuRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([])

  // Filter out dividers for keyboard nav
  const actionableItems = items.filter((item) => !item.divider)

  const close = useCallback(() => {
    if (!closing) {
      setClosing(true)
      setTimeout(() => {
        setClosing(false)
        setOpen(false)
        setMounted(false)
        setActiveIndex(-1)
      }, 120)
    }
  }, [closing])

  const toggleMenu = () => {
    if (disabled) return
    if (open) {
      close()
    } else {
      setMounted(true)
      setClosing(false)
      requestAnimationFrame(() => setOpen(true))
    }
  }

  // Click outside
  useEffect(() => {
    if (!open && !mounted) return
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        close()
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open, mounted, close])

  // Escape key
  useEffect(() => {
    if (!open) return
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close()
    }
    document.addEventListener('keydown', handleEscape as any)
    return () => document.removeEventListener('keydown', handleEscape as any)
  }, [open, close])

  // Focus first item on open
  useEffect(() => {
    if (open && actionableItems.length > 0) {
      setActiveIndex(0)
      requestAnimationFrame(() => itemRefs.current[0]?.focus())
    }
  }, [open])

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (!open) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
        e.preventDefault()
        toggleMenu()
      }
      return
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setActiveIndex((prev) => {
          const next = (prev + 1) % actionableItems.length
          itemRefs.current[next]?.focus()
          return next
        })
        break
      case 'ArrowUp':
        e.preventDefault()
        setActiveIndex((prev) => {
          const next = (prev - 1 + actionableItems.length) % actionableItems.length
          itemRefs.current[next]?.focus()
          return next
        })
        break
      case 'Enter':
      case ' ':
        e.preventDefault()
        if (activeIndex >= 0 && !actionableItems[activeIndex]?.disabled) {
          actionableItems[activeIndex]?.onClick?.()
          close()
        }
        break
      case 'Escape':
        e.preventDefault()
        close()
        break
    }
  }

  const handleItemClick = (item: DropdownItem) => {
    if (item.disabled) return
    item.onClick?.()
    close()
  }

  const show = open && !closing

  return (
    <div
      ref={containerRef}
      className={cn('relative inline-flex', className)}
      onKeyDown={handleKeyDown}
    >
      {/* Trigger */}
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={toggleMenu}
        className="inline-flex"
      >
        {trigger}
      </div>

      {/* Menu */}
      {(mounted || open) && (
        <div
          ref={menuRef}
          role="menu"
          className={cn(
            'absolute z-50 min-w-[180px] overflow-hidden',
            'bg-[var(--color-surface)] rounded-xl shadow-xl',
            'border border-[var(--color-border)]',
            'py-1',
            show ? 'animate-fade-in-scale' : 'animate-fade-out-scale',
            positionClasses[position],
            menuClassName
          )}
        >
          {/* Header */}
          {header && (
            <div className="px-3 py-2 border-b border-[var(--color-divider)] text-xs font-medium text-[var(--color-text-tertiary)]">
              {header}
            </div>
          )}

          {/* Items */}
          {items.map((item, index) => {
            if (item.divider) {
              return (
                <div
                  key={item.id}
                  className="my-1 mx-2 border-t border-[var(--color-divider)]"
                  aria-hidden="true"
                />
              )
            }

            return (
              <button
                key={item.id}
                ref={(el) => { itemRefs.current[index] = el }}
                role="menuitem"
                disabled={item.disabled}
                onClick={() => handleItemClick(item)}
                className={cn(
                  'flex items-center gap-3 w-full px-3 py-2 text-sm text-left',
                  'motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)]',
                  'focus-visible:outline-none',
                  item.danger
                    ? 'text-[var(--color-danger)] hover:bg-[var(--color-danger-light)] focus-visible:bg-[var(--color-danger-light)]'
                    : 'text-[var(--color-text-primary)] hover:bg-[var(--color-surface-hover)] focus-visible:bg-[var(--color-surface-hover)]',
                  item.disabled && 'opacity-40 cursor-not-allowed hover:bg-transparent'
                )}
              >
                {item.icon && (
                  <span className="h-4 w-4 flex-shrink-0 text-[var(--color-text-tertiary)]" aria-hidden="true">
                    {item.icon}
                  </span>
                )}
                <span className="flex-1 truncate">{item.label}</span>
                {item.shortcut && (
                  <span className="text-xs text-[var(--color-text-muted)] font-mono">{item.shortcut}</span>
                )}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
