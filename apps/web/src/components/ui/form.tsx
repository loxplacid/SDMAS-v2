import type { FormEvent, ReactNode } from 'react'
import { cn } from '../../lib/utils'

interface FormProps {
  onSubmit: (e: FormEvent) => void
  children: ReactNode
  className?: string
  spacing?: 'compact' | 'normal' | 'relaxed'
}

const spacings = {
  compact: 'space-y-3',
  normal: 'space-y-4',
  relaxed: 'space-y-6',
}

export function Form({ onSubmit, children, className = '', spacing = 'normal' }: FormProps) {
  return (
    <form onSubmit={onSubmit} className={cn(spacings[spacing], className)}>
      {children}
    </form>
  )
}
