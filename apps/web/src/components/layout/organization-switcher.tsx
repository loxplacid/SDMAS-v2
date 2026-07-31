import { DropdownMenu } from '../ui/dropdown-menu'
import type { DropdownItem } from '../ui/dropdown-menu'
import { Tooltip } from '../ui/tooltip'

const orgItems: DropdownItem[] = [
  {
    id: 'current-org',
    label: 'SDMAS International School',
    icon: (
      <span className="flex items-center justify-center h-5 w-5 rounded-md bg-[var(--color-brand-accent)] text-[8px] font-bold text-white">S</span>
    ),
    onClick: () => {},
  },
  { id: 'divider-1', label: '', divider: true },
  {
    id: 'manage-orgs',
    label: 'Manage Organizations',
    icon: (
      <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
    onClick: () => {},
  },
]

export function OrganizationSwitcher() {
  return (
    <DropdownMenu
      items={orgItems}
      position="bottom-left"
      trigger={
        <Tooltip content="Switch organization">
          <button className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs font-medium text-[var(--color-text-tertiary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-secondary)] motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)] border border-[var(--color-border)]" aria-label="Switch organization">
            <span className="flex items-center justify-center h-5 w-5 rounded-md bg-[var(--color-brand-accent)] text-[8px] font-bold text-white">S</span>
            <span className="hidden md:inline">SDMAS School</span>
            <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </Tooltip>
      }
    />
  )
}
