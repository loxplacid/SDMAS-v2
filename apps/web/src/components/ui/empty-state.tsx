import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

interface EmptyStateProps {
  title?: string
  description?: string
  action?: { label: string; onClick: () => void }
  icon?: ReactNode
  compact?: boolean
}

const defaultIcons: Record<string, string> = {
  students: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197',
  attendance: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2',
  fees: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2',
  academic: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3',
  payments: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1',
  teachers: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
  reports: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10',
  data: 'M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4',
}

export type DomainContext = keyof typeof defaultIcons

const contextualMessages: Record<string, { title: string; description: string }> = {
  admissions: { title: 'No admissions yet', description: 'Your admissions pipeline is empty. Create your first inquiry to start tracking prospective students.' },
  students: { title: 'No students yet', description: 'Your student directory is empty. Add your first student to begin building your school.' },
  attendance: { title: 'No attendance records', description: 'Attendance data will appear here once records are created.' },
  fees: { title: 'No fee data', description: 'Fee information will appear once fee types and structures are configured.' },
  academic: { title: 'No academic data', description: 'Configure academic years, classes, and sections to build your school\'s academic structure.' },
  payments: { title: 'No payments recorded', description: 'Payment records will appear once fee payments are processed.' },
  teachers: { title: 'No teachers yet', description: 'Add teaching staff to begin assigning them to classes and subjects.' },
  reports: { title: 'No reports available', description: 'Generate attendance or fee reports to view summaries here.' },
  data: { title: 'No data found', description: 'The data you are looking for is not available yet.' },
}

export function EmptyState({ title, description, action, icon, compact = false }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center text-center animate-fade-in-up">
      <div className={compact ? 'py-8' : 'py-16'}>
        {icon || (
          <div className={cn('mx-auto rounded-2xl bg-[var(--color-bg)] flex items-center justify-center', compact ? 'h-10 w-10' : 'h-14 w-14')}>
            <svg className={compact ? 'h-5 w-5' : 'h-7 w-7'} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
            </svg>
          </div>
        )}
        <h3 className={cn('font-semibold text-[var(--color-text-primary)]', compact ? 'text-sm mt-3' : 'text-base mt-5')}>
          {title || 'No data found'}
        </h3>
        {description && (
          <p className={cn('text-[var(--color-text-tertiary)] max-w-sm mx-auto leading-relaxed', compact ? 'text-xs mt-1' : 'text-sm mt-1.5')}>
            {description}
          </p>
        )}
        {action && (
          <button
            onClick={action.onClick}
            className="inline-flex items-center gap-2 rounded-[10px] bg-[var(--color-brand-accent)] px-4 py-2.5 text-sm font-medium text-white hover:bg-[var(--color-brand-accent-hover)] motion-safe:transition-colors mt-6"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            {action.label}
          </button>
        )}
      </div>
    </div>
  )
}

export function getEmptyState(domain: DomainContext): { title: string; description: string; icon: string } {
  const msg = contextualMessages[domain] || contextualMessages.data
  return {
    title: msg.title,
    description: msg.description,
    icon: defaultIcons[domain] || defaultIcons.data,
  }
}
