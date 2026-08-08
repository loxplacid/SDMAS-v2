import {
  useState,
  useRef,
  useEffect,
  type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'
import { cn } from '../../lib/utils'

type TooltipPosition = 'top' | 'bottom' | 'left' | 'right'

interface TooltipProps {
  content: ReactNode
  children: ReactNode
  position?: TooltipPosition
  delay?: number
  className?: string
  contentClassName?: string
  disabled?: boolean
  /**
   * Render the tooltip through a portal to <body>, positioned with `fixed`
   * at the trigger's measured coordinates. Use inside scroll/overflow
   * containers (the collapsed sidebar rail, drawers) where an absolutely
   * positioned tooltip would be clipped by ancestor overflow.
   */
  portal?: boolean
}

const positionClasses: Record<TooltipPosition, string> = {
  top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
  bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
  left: 'right-full top-1/2 -translate-y-1/2 mr-2',
  right: 'left-full top-1/2 -translate-y-1/2 ml-2',
}

const arrowClasses: Record<TooltipPosition, string> = {
  top: 'top-full left-1/2 -translate-x-1/2 border-l-[5px] border-r-[5px] border-t-[5px] border-l-transparent border-r-transparent border-t-[var(--color-text-primary)]',
  bottom: 'bottom-full left-1/2 -translate-x-1/2 border-l-[5px] border-r-[5px] border-b-[5px] border-l-transparent border-r-transparent border-b-[var(--color-text-primary)]',
  left: 'left-full top-1/2 -translate-y-1/2 border-t-[5px] border-b-[5px] border-l-[5px] border-t-transparent border-b-transparent border-l-[var(--color-text-primary)]',
  right: 'right-full top-1/2 -translate-y-1/2 border-t-[5px] border-b-[5px] border-r-[5px] border-t-transparent border-b-transparent border-r-[var(--color-text-primary)]',
}

const tooltipSurfaceClasses =
  'px-3 py-1.5 rounded-[var(--radius-md)] bg-[var(--color-text-primary)] text-[var(--color-text-inverse)] text-xs font-medium leading-tight whitespace-nowrap shadow-lg'

export function Tooltip({
  content,
  children,
  position = 'top',
  delay = 400,
  className,
  contentClassName,
  disabled = false,
  portal = false,
}: TooltipProps) {
  const [visible, setVisible] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [anchor, setAnchor] = useState<{ x: number; y: number } | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const triggerRef = useRef<HTMLDivElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  const show = () => {
    if (disabled) return
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      if (portal && triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect()
        setAnchor({ x: rect.left + rect.width + 12, y: rect.top + rect.height / 2 })
      }
      setMounted(true)
      requestAnimationFrame(() => setVisible(true))
    }, delay)
  }

  const hide = () => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setVisible(false)
    // Keep mounted briefly for the exit animation.
    setTimeout(() => setMounted(false), 100)
  }

  const trigger = (
    <div
      ref={triggerRef}
      className={cn('relative inline-flex', className)}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {!portal && mounted && (
        <div
          ref={tooltipRef}
          role="tooltip"
          className={cn(
            'absolute z-[var(--z-tooltip)] pointer-events-none',
            tooltipSurfaceClasses,
            positionClasses[position],
            visible ? 'animate-fade-in-up' : 'animate-fade-out-up',
            contentClassName
          )}
        >
          {content}
          <span
            className={cn('absolute w-0 h-0', arrowClasses[position])}
            aria-hidden="true"
          />
        </div>
      )}
    </div>
  )

  if (portal && mounted && anchor && typeof document !== 'undefined') {
    return (
      <>
        {trigger}
        {createPortal(
          <div
            ref={tooltipRef}
            role="tooltip"
            className={cn(
              'fixed z-[var(--z-portal)] pointer-events-none',
              tooltipSurfaceClasses,
              visible ? 'animate-fade-in-up' : 'animate-fade-out-up',
              contentClassName
            )}
            style={{ left: anchor.x, top: anchor.y, transform: 'translateY(-50%)' }}
          >
            {content}
          </div>,
          document.body
        )}
      </>
    )
  }

  return trigger
}
