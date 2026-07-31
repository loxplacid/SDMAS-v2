import { useId } from 'react'
import { cn, capitalize } from '../../lib/utils'

/** All available roles in the system for selection. */
const ALL_ROLES = [
  { value: 'admin', label: 'Administrator', description: 'Full system access' },
  { value: 'principal', label: 'Principal', description: 'School leadership overview' },
  { value: 'accountant', label: 'Accountant', description: 'Financial management' },
  { value: 'staff', label: 'Staff', description: 'General staff access' },
  { value: 'teacher', label: 'Teacher', description: 'Classes, attendance & students' },
  { value: 'student', label: 'Student', description: 'My attendance, fees & schedule' },
  { value: 'parent', label: 'Parent', description: 'Children overview & payments' },
] as const

const ROLE_COLORS: Record<string, string> = {
  admin: 'bg-[var(--color-brand-accent)]',
  principal: 'bg-indigo-500',
  accountant: 'bg-blue-500',
  staff: 'bg-teal-500',
  teacher: 'bg-emerald-500',
  student: 'bg-violet-500',
  parent: 'bg-amber-500',
}

interface RoleMultiSelectProps {
  /** Currently selected role codes. */
  selected: string[]
  /** Called whenever the selection changes. */
  onChange: (selected: string[]) => void
  /** The user's primary role — shown at the top and visually distinct. */
  primaryRole?: string
  /** Optional label displayed above the checkbox group. */
  label?: string
  /** Error message to display. */
  error?: string
  /** Disable the entire control. */
  disabled?: boolean
}

/**
 * Multi-select checkbox group for assigning roles to a user.
 *
 * The user's primary role (from the ``role`` field) is shown separately
 * and cannot be unchecked. Additional roles are managed via checkboxes.
 *
 * @example
 * ```tsx
 * const [roles, setRoles] = useState(['staff'])
 * <RoleMultiSelect
 *   selected={roles}
 *   onChange={setRoles}
 *   primaryRole="staff"
 *   label="Additional Roles"
 * />
 * ```
 */
export function RoleMultiSelect({
  selected,
  onChange,
  primaryRole,
  label,
  error,
  disabled = false,
}: RoleMultiSelectProps) {
  const baseId = useId()

  const toggle = (roleValue: string) => {
    // Never allow unchecking the primary role
    if (roleValue === primaryRole) return

    const next = selected.includes(roleValue)
      ? selected.filter((r) => r !== roleValue)
      : [...selected, roleValue]
    onChange(next)
  }

  return (
    <div className="space-y-1.5">
      {label && (
        <p className="block text-sm font-medium text-[var(--color-text-primary)] leading-snug">
          {label}
        </p>
      )}

      <fieldset
        className={cn(
          'rounded-[10px] border border-[var(--color-border)] p-3 space-y-1',
          'motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)]',
          disabled && 'bg-[var(--color-surface-hover)] opacity-60 cursor-not-allowed',
          error && 'border-[var(--color-danger)]',
        )}
        disabled={disabled}
      >
        <legend className="sr-only">Role selection</legend>

        {ALL_ROLES.map((role) => {
          const isPrimary = role.value === primaryRole
          const isChecked = selected.includes(role.value)
          const checkboxId = `${baseId}-role-${role.value}`

          return (
            <label
              key={role.value}
              htmlFor={checkboxId}
              className={cn(
                'flex items-start gap-3 rounded-lg px-3 py-2.5 cursor-pointer',
                'motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)]',
                isChecked
                  ? 'bg-[var(--color-brand-accent-bg)]'
                  : 'hover:bg-[var(--color-surface-hover)]',
                isPrimary && 'ring-1 ring-[var(--color-brand-accent-ring)]',
              )}
            >
              <input
                type="checkbox"
                id={checkboxId}
                checked={isChecked}
                onChange={() => toggle(role.value)}
                disabled={disabled || isPrimary}
                className={cn(
                  'mt-0.5 h-4 w-4 rounded border-[var(--color-border)]',
                  'text-[var(--color-brand-accent)] focus:ring-[var(--color-brand-accent-ring)]',
                  'motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)]',
                )}
              />

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      'h-2 w-2 rounded-full shrink-0',
                      ROLE_COLORS[role.value] || 'bg-[var(--color-text-muted)]',
                    )}
                    aria-hidden="true"
                  />
                  <span className="text-sm font-medium text-[var(--color-text-primary)]">
                    {role.label}
                  </span>
                  {isPrimary && (
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider bg-[var(--color-brand-accent)] text-white">
                      Primary
                    </span>
                  )}
                </div>
                <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5 leading-snug line-clamp-1">
                  {role.description}
                </p>
              </div>
            </label>
          )
        })}
      </fieldset>

      {error && (
        <p className="text-xs text-[var(--color-danger)] animate-slide-down leading-snug" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
