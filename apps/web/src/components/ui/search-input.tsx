import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

interface SearchInputProps extends InputHTMLAttributes<HTMLInputElement> {
  onClear?: () => void
  showKbdHint?: boolean
}

export const SearchInput = forwardRef<HTMLInputElement, SearchInputProps>(
  function SearchInput({ className, onClear, value, onChange, showKbdHint, ...props }, ref) {
    return (
      <div className="relative">
        <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
          <svg
            className="h-4 w-4 text-[var(--color-text-muted)]"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        </div>
        <input
          ref={ref}
          type="search"
          value={value}
          onChange={onChange}
          className={cn(
            'block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] pl-9 pr-8 py-2 text-sm',
            'text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)]',
            'motion-safe:transition-all motion-safe:duration-[var(--motion-fast)]',
            'focus-visible:border-[var(--color-brand-accent)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-brand-accent-ring)]',
            'hover:border-[var(--color-border-hover)]',
            className
          )}
          {...props}
        />
        {/* / kbd hint — shown when empty and not focused */}
        {showKbdHint && !value && (
          <kbd className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none text-[10px] font-medium text-[var(--color-text-muted)]">
            <span className="inline-flex items-center justify-center h-4 min-w-[18px] px-1 rounded bg-[var(--color-bg)] border border-[var(--color-border)]">/</span>
          </kbd>
        )}
        {value && onClear && (
          <button
            onClick={onClear}
            className="absolute inset-y-0 right-0 flex items-center pr-3 text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]"
            aria-label="Clear search"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>
    )
  }
)
