import { useNavigate } from 'react-router-dom'
import { DropdownMenu } from '../ui/dropdown-menu'
import type { DropdownItem } from '../ui/dropdown-menu'
import { Tooltip } from '../ui/tooltip'

interface QuickCreateProps {
  buttonClassName?: string
}

export function QuickCreate({ buttonClassName }: QuickCreateProps) {
  const navigate = useNavigate()

  const quickItems: DropdownItem[] = [
    {
      id: 'add-student',
      label: 'New Student',
      icon: (
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
        </svg>
      ),
      onClick: () => navigate('/admissions/new'),
    },
    {
      id: 'record-attendance',
      label: 'Record Attendance',
      icon: (
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
        </svg>
      ),
      onClick: () => navigate('/attendance/daily'),
    },
    { id: 'divider-1', label: '', divider: true },
    {
      id: 'record-payment',
      label: 'Record Payment',
      icon: (
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
        </svg>
      ),
      onClick: () => navigate('/fees/payments'),
    },
    {
      id: 'batch-enroll',
      label: 'Batch Enroll',
      icon: (
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      ),
      onClick: () => navigate('/operations/batch/enroll'),
    },
  ]

  return (
    <DropdownMenu
      items={quickItems}
      position="bottom-right"
      header={
        <p className="text-xs font-semibold text-[var(--color-text-primary)]">Quick Create</p>
      }
      trigger={
        <Tooltip content="Quick create (c)">
          <button
            className={buttonClassName || 'flex items-center justify-center h-8 w-8 rounded-xl bg-[var(--color-brand-accent)] text-white hover:bg-[var(--color-brand-accent-hover)] motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)] shadow-sm'}
            aria-label="Quick create"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
          </button>
        </Tooltip>
      }
    />
  )
}
