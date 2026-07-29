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
      {formatted}
    </span>
  )
}
