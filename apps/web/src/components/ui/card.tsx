import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

interface CardProps {
  title?: string
  children: ReactNode
  className?: string
  actions?: ReactNode
  onClick?: () => void
}

export function Card({ title, children, className, actions, onClick }: CardProps) {
  return (
    <div
      className={cn(
        'bg-white rounded-lg border border-gray-200 shadow-sm',
        onClick && 'cursor-pointer hover:shadow-md transition-shadow',
        className
      )}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') onClick() } : undefined}
    >
      {(title || actions) && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          {title && <h3 className="text-lg font-medium text-gray-900">{title}</h3>}
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  )
}