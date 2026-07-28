import { cn } from '../../lib/utils'

interface LoadingProps {
  text?: string
  className?: string
}

export function Loading({ text = 'Loading...', className }: LoadingProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-12', className)}>
      <svg className="animate-spin h-8 w-8 text-blue-600 mb-3" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      <p className="text-gray-500 text-sm">{text}</p>
    </div>
  )
}