import { useEffect, useRef, useState, type ReactNode, type MouseEvent, useCallback } from 'react'
import { cn } from '../../lib/utils'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  footer?: ReactNode
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full'
}

const sizeClasses = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
  full: 'max-w-[95vw]',
}

export function Modal({ open, onClose, title, children, footer, size = 'md' }: ModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null)
  const dialogRef = useRef<HTMLDivElement>(null)
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
      }, 150)
    }
  }, [onClose, closing])

  const handleEscape = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose()
    },
    [handleClose]
  )

  useEffect(() => {
    if (open) {
      setMounted(true)
      setClosing(false)
      previousFocusRef.current = document.activeElement as HTMLElement
      document.addEventListener('keydown', handleEscape)
      document.body.style.overflow = 'hidden'

      // Focus the dialog
      requestAnimationFrame(() => dialogRef.current?.focus())

      return () => {
        document.removeEventListener('keydown', handleEscape)
        document.body.style.overflow = ''
        previousFocusRef.current?.focus()
      }
    }
  }, [open, handleEscape])

  if (!mounted && !open) return null

  const handleOverlayClick = (e: MouseEvent) => {
    if (e.target === overlayRef.current && !closing) handleClose()
  }

  const show = open && !closing

  return (
    <div
      ref={overlayRef}
      className={cn(
        'fixed inset-0 z-50 flex items-center justify-center p-4',
        show ? 'animate-fade-in' : 'animate-fade-out'
      )}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" aria-hidden="true" />
      <div
        ref={dialogRef}
        tabIndex={-1}
        className={cn(
          'relative bg-[var(--color-surface)] rounded-xl shadow-xl w-full',
          show ? 'animate-scale-in' : 'animate-scale-out',
          'max-h-[90vh] overflow-y-auto',
          sizeClasses[size]
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)]">
          <h2 id="modal-title" className="text-lg font-semibold text-[var(--color-text-primary)]">
            {title}
          </h2>
          <button
            onClick={handleClose}
            className="flex items-center justify-center h-8 w-8 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-hover)] transition-colors"
            aria-label="Close"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5">{children}</div>

        {/* Footer */}
        {footer && (
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-[var(--color-border)] bg-[var(--color-bg)] rounded-b-xl">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}
