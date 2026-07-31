import { forwardRef, type SelectHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  options: { value: string; label: string }[]
  placeholder?: string
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  function Select({ label, error, options, placeholder, className, id, ...props }, ref) {
    const selectId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined)
    return (
      <div className="space-y-1.5">
        {label && (
          <label
            htmlFor={selectId}
            className="block text-sm font-medium text-[var(--color-text-primary)] leading-snug"
          >
            {label}
          </label>
        )}
        <div className="relative">
          <select
            ref={ref}
            id={selectId}
            className={cn(
              'block w-full rounded-[10px] border bg-[var(--color-surface)] pl-3.5 pr-9 py-2.5 text-sm appearance-none',
              'text-[var(--color-text-primary)]',
              'motion-safe:transition-all motion-safe:duration-[var(--motion-fast)] motion-safe:ease-[var(--ease-standard)]',
              'focus-visible:outline-none',
              error
                ? 'border-[var(--color-danger)] focus-visible:border-[var(--color-danger)] focus-visible:ring-2 focus-visible:ring-[var(--color-danger-ring)]'
                : 'border-[var(--color-border)] hover:border-[var(--color-border-hover)] focus-visible:border-[var(--color-brand-accent)] focus-visible:ring-2 focus-visible:ring-[var(--color-brand-accent-ring)]',
              'disabled:bg-[var(--color-surface-hover)] disabled:cursor-not-allowed disabled:opacity-50',
              className
            )}
            aria-invalid={error ? 'true' : undefined}
            {...props}
          >
            {placeholder && (
              <option value="" disabled>
                {placeholder}
              </option>
            )}
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3.5">
            <svg className="h-4 w-4 text-[var(--color-text-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>
        {error && (
          <p className="text-xs text-[var(--color-danger)] animate-slide-down leading-snug" role="alert">
            {error}
          </p>
        )}
      </div>
    )
  }
)
