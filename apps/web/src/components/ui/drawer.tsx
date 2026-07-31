import { useEffect, useRef, useState, type ReactNode, type MouseEvent, useCallback } from 'react'
import { cn } from '../../lib/utils'

interface DrawerProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  footer?: ReactNode
  side?: 'right' | 'left'
  size?: 'sm' | 'md' | 'lg' | 'full'
  panelClassName?: string
  headerClassName?: string
}

const sizeClasses: Record<string, string> = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  full: 'max-w-full',
}

export function Drawer({
  open,
  onClose,
  title,
  children,
  footer,
  side = 'right',
  size = 'md',
  panelClassName,
  headerClassName,
}: DrawerProps) {
  const overlayRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)
  const [closing, setClosing] = useState(false)
  const [mounted, setMounted] = useState(false)

  const handleClose = useCallback(() => {
    if (!closing) {
      setClosing(true)
      setTimeout(() => {
        setClosing(false)
        setMounted(false)
        onClose()
      }, 200)
    }
  }, [onClose, closing])

  useEffect(() => {
    function handleEscape(e: KeyboardEvent) {
      if (e.key === 'Escape') handleClose()
    }
    if (open) {
      setMounted(true)
      setClosing(false)
      previousFocusRef.current = document.activeElement as HTMLElement
      document.addEventListener('keydown', handleEscape)
      document.body.style.overflow = 'hidden'
      requestAnimationFrame(() => panelRef.current?.focus())
      return () => {
        document.removeEventListener('keydown', handleEscape)
        document.body.style.overflow = ''
        previousFocusRef.current?.focus()
      }
    }
  }, [open, handleClose])

  if (!mounted && !open) return null

  const handleOverlayClick = (e: MouseEvent) => {
    if (e.target === overlayRef.current && !closing) handleClose()
  }

  const show = open && !closing

  const slideAnimation = side === 'right'
    ? show ? 'animate-drawer-in' : 'animate-slide-out-right'
    : show ? 'animate-slide-in-left' : 'animate-slide-out-left'

  return (
    <div
      ref={overlayRef}
      className={cn(
        'fixed inset-0 z-50 flex',
        side === 'right' ? 'justify-end' : 'justify-start'
      )}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="drawer-title"
    >
      {/* Backdrop */}
      <div
        className={cn(
          'fixed inset-0 bg-[var(--color-surface-overlay)] backdrop-blur-[3px]',
          show ? 'animate-drawer-overlay-in' : 'animate-fade-out'
        )}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        ref={panelRef}
        tabIndex={-1}
        className={cn(
          'relative w-full h-full shadow-2xl',
          'flex flex-col',
          'focus-visible:outline-none',
          slideAnimation,
          sizeClasses[size],
          side === 'right' ? 'rounded-l-2xl' : 'rounded-r-2xl',
          panelClassName || 'bg-[var(--color-surface)]'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-divider)] shrink-0">
          <h2
            id="drawer-title"
            className={cn(
              'text-lg font-semibold leading-snug',
              headerClassName || 'text-[var(--color-text-primary)]'
            )}
          >
            {title}
          </h2>
          <button
            onClick={handleClose}
            className={cn(
              'flex items-center justify-center h-8 w-8 rounded-xl motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)]',
              headerClassName
                ? 'text-white/60 hover:text-white hover:bg-white/10'
                : 'text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-hover)]'
            )}
            aria-label="Close drawer"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-[var(--color-divider)] bg-[var(--color-bg)] shrink-0">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}
