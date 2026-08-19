import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  hint?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  function Input({ label, error, hint, className, id, ...props }, ref) {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined)
    return (
      <div className="space-y-1.5">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-sm font-medium text-[var(--color-text-primary)] leading-snug"
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={cn(
            'block w-full rounded-lg border bg-[var(--color-surface)] px-3.5 py-2.5 text-sm',
            'text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)]',
            'motion-safe:transition-all motion-safe:duration-[var(--motion-fast)] motion-safe:ease-[var(--ease-standard)]',
            'focus-visible:outline-none',
            error
              ? 'border-[var(--color-danger)] focus-visible:border-[var(--color-danger)] focus-visible:ring-2 focus-visible:ring-[var(--color-danger-ring)]'
              : 'border-[var(--color-border)] hover:border-[var(--color-border-hover)] focus-visible:border-[var(--color-brand-accent)] focus-visible:ring-2 focus-visible:ring-[var(--color-brand-accent-ring)]',
            'disabled:bg-[var(--color-surface-hover)] disabled:cursor-not-allowed disabled:opacity-50',
            className
          )}
          aria-invalid={error ? 'true' : undefined}
          aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
          {...props}
        />
        {error && (
          <p id={`${inputId}-error`} className="text-xs text-[var(--color-danger)] animate-slide-down leading-snug" role="alert">
            {error}
          </p>
        )}
        {hint && !error && (
          <p id={`${inputId}-hint`} className="text-xs text-[var(--color-text-tertiary)] animate-fade-in leading-snug">
            {hint}
          </p>
        )}
      </div>
    )
  }
)
