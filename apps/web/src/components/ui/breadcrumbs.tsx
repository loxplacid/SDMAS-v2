import { Link } from 'react-router-dom'

interface Crumb { label: string; href?: string }
interface BreadcrumbsProps { items: Crumb[] }

export function Breadcrumbs({ items }: BreadcrumbsProps) {
  return (
    <nav aria-label="Breadcrumb" className="mb-4 animate-fade-in">
      <ol className="flex items-center gap-1.5 text-sm text-[var(--color-text-tertiary)]">
        {items.map((item, idx) => {
          const isLast = idx === items.length - 1
          return (
            <li key={idx} className="flex items-center gap-1.5" style={{ animationDelay: `${idx * 50}ms`, animationFillMode: 'both' }}>
              {idx > 0 && (
                <svg className="h-3.5 w-3.5 flex-shrink-0 text-[var(--color-text-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              )}
              {isLast || !item.href ? (
                <span className={isLast ? 'font-semibold text-[var(--color-text-primary)]' : ''} aria-current={isLast ? 'page' : undefined}>
                  {item.label}
                </span>
              ) : (
                <Link to={item.href} className="hover:text-[var(--color-text-primary)] motion-safe:transition-colors">
                  {item.label}
                </Link>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
