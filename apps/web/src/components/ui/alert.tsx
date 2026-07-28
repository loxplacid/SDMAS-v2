import type { ReactNode } from 'react'

interface AlertProps {
  variant?: 'info' | 'success' | 'warning' | 'error'
  children: ReactNode
  onClose?: () => void
  className?: string
}

const variants = {
  info: 'bg-blue-50 border-blue-200 text-blue-800',
  success: 'bg-green-50 border-green-200 text-green-800',
  warning: 'bg-yellow-50 border-yellow-200 text-yellow-800',
  error: 'bg-red-50 border-red-200 text-red-800',
}

export function Alert({ variant = 'info', children, onClose, className = '' }: AlertProps) {
  return (
    <div className={`rounded-md border p-3 text-sm ${variants[variant]} ${className}`}>
      <div className="flex items-start justify-between">
        <div>{children}</div>
        {onClose && (
          <button onClick={onClose} className="ml-2 text-current hover:opacity-70">&times;</button>
        )}
      </div>
    </div>
  )
}