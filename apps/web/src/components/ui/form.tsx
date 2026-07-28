import type { FormEvent, ReactNode } from 'react'

interface FormProps {
  onSubmit: (e: FormEvent) => void
  children: ReactNode
  className?: string
}

export function Form({ onSubmit, children, className = '' }: FormProps) {
  return (
    <form onSubmit={onSubmit} className={`space-y-4 ${className}`}>
      {children}
    </form>
  )
}