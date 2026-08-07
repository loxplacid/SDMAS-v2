import { useState, useEffect, useRef } from 'react'
import { cn } from '../../lib/utils'

interface AnimatedCountProps {
  value: number
  duration?: number
  formatter?: (value: number) => string
  className?: string
  decimals?: number
  prefix?: string
  suffix?: string
}

const easeOutCubic = (t: number): number => {
  return 1 - Math.pow(1 - t, 3)
}

export function AnimatedCount({
  value,
  duration = 1200,
  formatter,
  className,
  decimals = 0,
  prefix = '',
  suffix = '',
}: AnimatedCountProps) {
  const [displayValue, setDisplayValue] = useState(0)
  const frameRef = useRef<number | null>(null)
  const startTimeRef = useRef<number | null>(null)
  const startValueRef = useRef(0)
  // Glint §3.3 counter settle: a one-shot spring pop on the numeral when the
  // roll finishes. `settleKey` changes per *update* (never the initial mount);
  // the settle class is gated on `settleKey > 0` so the animation never plays
  // on first paint — only on genuine value changes.
  const prevValueRef = useRef<number | null>(null)
  const [settleKey, setSettleKey] = useState(0)

  // Settle trigger lives on the value change, not inside the roll's rAF
  // completion — under reduced motion the roll is instant (no rAF runs), so
  // the pop must still fire (and under the global kill-switch its animation
  // resolves instantly to the end state, so it costs nothing).
  useEffect(() => {
    const previous = prevValueRef.current
    prevValueRef.current = value
    if (previous !== null && previous !== value) {
      setSettleKey((k) => k + 1)
    }
  }, [value])

  useEffect(() => {
    // Respect reduced motion
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (prefersReducedMotion) {
      setDisplayValue(value)
      return
    }

    startValueRef.current = displayValue
    startTimeRef.current = null

    const animate = (timestamp: number) => {
      if (startTimeRef.current === null) {
        startTimeRef.current = timestamp
      }

      const elapsed = timestamp - startTimeRef.current
      const progress = Math.min(elapsed / duration, 1)
      const easedProgress = easeOutCubic(progress)

      const current = startValueRef.current + (value - startValueRef.current) * easedProgress
      setDisplayValue(current)

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate)
      } else {
        setDisplayValue(value)
      }
    }

    frameRef.current = requestAnimationFrame(animate)

    return () => {
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current)
      }
    }
  }, [value, duration])

  const formatted = formatter
    ? formatter(displayValue)
    : `${prefix}${displayValue.toFixed(decimals)}${suffix}`

  return (
    <span
      className={cn('tabular-nums', className)}
      aria-label={`${prefix}${value}${suffix}`}
    >
      <span
        key={settleKey}
        className={cn('inline-block', settleKey > 0 && 'animate-counter-settle')}
        aria-hidden="true"
      >
        {formatted}
      </span>
    </span>
  )
}
