import { useState, useRef, useEffect, type ReactNode, type KeyboardEvent } from 'react'
import { cn } from '../../lib/utils'

export interface Tab {
  id: string
  label: string
  icon?: ReactNode
  badge?: ReactNode
  disabled?: boolean
}

interface TabGroupProps {
  tabs: Tab[]
  activeTab?: string
  defaultTab?: string
  onChange?: (tabId: string) => void
  variant?: 'underline' | 'pills'
  size?: 'sm' | 'md' | 'lg'
  className?: string
  children?: ReactNode
}

const variantStyles = {
  underline: {
    container: 'border-b border-[var(--color-divider)]',
    tab: (active: boolean) =>
      cn(
        'relative inline-flex items-center gap-2 whitespace-nowrap font-medium motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)]',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-brand-accent-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg)] rounded-[var(--radius-sm)]',
        active
          ? 'text-[var(--color-brand-accent)]'
          : 'text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]'
      ),
    indicator: 'absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--color-brand-accent)] animate-active-indicator',
  },
  pills: {
    container: 'inline-flex gap-1 p-1 bg-[var(--color-surface-hover)] rounded-[var(--radius-lg)]',
    tab: (active: boolean) =>
      cn(
        'relative inline-flex items-center gap-2 whitespace-nowrap font-medium rounded-[var(--radius-md)] motion-safe:transition-all motion-safe:duration-[var(--motion-fast)]',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-brand-accent-ring)]',
        active
          ? 'bg-[var(--color-surface)] text-[var(--color-text-primary)] shadow-sm'
          : 'text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]'
      ),
    indicator: '', // no separate indicator for pills
  },
}

const sizeStyles = {
  underline: {
    sm: 'px-3 py-2 text-xs',
    md: 'px-4 py-2.5 text-sm',
    lg: 'px-5 py-3 text-[15px]',
  },
  pills: {
    sm: 'px-2.5 py-1.5 text-xs',
    md: 'px-3 py-2 text-sm',
    lg: 'px-4 py-2.5 text-[15px]',
  },
}

export function TabGroup({
  tabs,
  activeTab: controlledActive,
  defaultTab,
  onChange,
  variant = 'underline',
  size = 'md',
  className,
}: TabGroupProps) {
  const isControlled = controlledActive !== undefined
  const [internalActive, setInternalActive] = useState(defaultTab ?? tabs[0]?.id ?? '')
  const activeTab = isControlled ? controlledActive : internalActive

  const tabRefs = useRef<Map<string, HTMLButtonElement>>(new Map())
  const containerRef = useRef<HTMLDivElement>(null)

  // Focus the active tab on mount
  useEffect(() => {
    const btn = tabRefs.current.get(activeTab)
    if (btn) btn.focus()
  }, [activeTab])

  const handleTabClick = (tabId: string) => {
    if (!isControlled) setInternalActive(tabId)
    onChange?.(tabId)
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let newIndex = index
    if (e.key === 'ArrowRight') {
      e.preventDefault()
      newIndex = (index + 1) % tabs.length
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault()
      newIndex = (index - 1 + tabs.length) % tabs.length
    } else if (e.key === 'Home') {
      e.preventDefault()
      newIndex = 0
    } else if (e.key === 'End') {
      e.preventDefault()
      newIndex = tabs.length - 1
    } else {
      return
    }

    // Skip disabled tabs
    let targetIndex = newIndex
    if (tabs[targetIndex]?.disabled) {
      if (e.key === 'ArrowRight' || e.key === 'Home') {
        targetIndex = (targetIndex + 1) % tabs.length
      } else {
        targetIndex = (targetIndex - 1 + tabs.length) % tabs.length
      }
    }

    const targetTab = tabs[targetIndex]
    if (targetTab && !targetTab.disabled) {
      handleTabClick(targetTab.id)
      tabRefs.current.get(targetTab.id)?.focus()
    }
  }

  const vs = variantStyles[variant]
  const ss = sizeStyles[variant]

  return (
    <div
      ref={containerRef}
      className={cn(vs.container, className)}
      role="tablist"
      aria-orientation="horizontal"
    >
      <div className="flex items-center gap-0">
        {tabs.map((tab, index) => {
          const isActive = tab.id === activeTab
          return (
            <button
              key={tab.id}
              ref={(el) => {
                if (el) tabRefs.current.set(tab.id, el)
                else tabRefs.current.delete(tab.id)
              }}
              role="tab"
              aria-selected={isActive}
              aria-disabled={tab.disabled}
              tabIndex={isActive ? 0 : -1}
              disabled={tab.disabled}
              onClick={() => handleTabClick(tab.id)}
              onKeyDown={(e) => handleKeyDown(e, index)}
              className={cn(
                vs.tab(isActive),
                ss[size],
                tab.disabled && 'opacity-40 cursor-not-allowed'
              )}
            >
              {tab.icon && (
                <span className="h-4 w-4 flex-shrink-0" aria-hidden="true">
                  {tab.icon}
                </span>
              )}
              {tab.label}
              {tab.badge && (
                <span className="flex-shrink-0">{tab.badge}</span>
              )}
              {variant === 'underline' && isActive && (
                <span className={vs.indicator} aria-hidden="true" />
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
