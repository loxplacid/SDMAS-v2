export const STUDENT_STATUSES = ['active', 'inactive', 'graduated', 'transferred'] as const
export const ACADEMIC_STATUSES = ['active', 'inactive'] as const
export const TEACHER_STATUSES = ['active', 'inactive'] as const
export const SUBJECT_STATUSES = ['active', 'inactive'] as const
export const ATTENDANCE_STATUSES = ['present', 'absent', 'late', 'excused'] as const
export const FEE_TYPE_STATUSES = ['active', 'inactive'] as const
export const FEE_STRUCTURE_STATUSES = ['active', 'inactive'] as const
export const FEE_DUE_STATUSES = ['unpaid', 'partially_paid', 'paid'] as const
export const ENROLLMENT_STATUSES = ['active', 'inactive'] as const
export const TERM_STATUSES = ['active', 'inactive'] as const
export const ADMISSION_STATUSES = [
  'inquiry',
  'application_submitted',
  'documents_uploaded',
  'verified',
  'interview_scheduled',
  'interview_completed',
  'merit_listed',
  'seat_allocated',
  'fee_paid',
  'enrolled',
  'student_created',
  'rejected',
] as const

export const PAYMENT_METHODS = ['cash', 'bank_transfer', 'cheque', 'card', 'mobile_money', 'other'] as const
export const DEFAULT_PAGE_SIZE = 20

export function formatDate(date: string | null | undefined): string {
  if (!date) return '-'
  return new Date(date).toLocaleDateString()
}

export function formatDateTime(date: string | null | undefined): string {
  if (!date) return '-'
  return new Date(date).toLocaleString()
}

export function formatRelativeTime(date: string | Date): string {
  const then = typeof date === 'string' ? new Date(date) : date
  const diffMs = then.getTime() - Date.now()
  const absMs = Math.abs(diffMs)
  const minutes = Math.floor(absMs / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  const weeks = Math.floor(days / 7)
  if (weeks < 5) return `${weeks}w ago`
  const months = Math.floor(days / 30)
  if (months < 12) return `${months}mo ago`
  const years = Math.floor(days / 365)
  return `${years}y ago`
}

export function formatCurrency(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`
}

export function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1)
}

/**
 * Count + noun pair with automatic pluralisation, e.g. plural(1, 'term') →
 * "1 term", plural(3, 'term') → "3 terms". Pass an explicit plural form for
 * irregular nouns (plural(2, 'class', 'classes')). Counts are grouped with
 * thousands separators; pin a BCP-47 tag to force a currency-style grouping,
 * e.g. 'en-KE' — defaults to 'en-US' so output never varies by browser locale.
 */
export function plural(count: number, singular: string, pluralForm?: string, locale = 'en-US'): string {
  const word = count === 1 ? singular : (pluralForm ?? `${singular}s`)
  return `${count.toLocaleString(locale)} ${word}`
}

export function debounce<T extends (...args: any[]) => void>(fn: T, ms: number): T & { cancel: () => void } {
  let timer: ReturnType<typeof setTimeout>
  const debounced = (...args: any[]) => {
    clearTimeout(timer)
    timer = setTimeout(() => fn(...args), ms)
  }
  debounced.cancel = () => clearTimeout(timer)
  return debounced as T & { cancel: () => void }
}

export function cn(...classes: (string | boolean | undefined | null)[]): string {
  return classes.filter(Boolean).join(' ')
}