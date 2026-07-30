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

export function formatCurrency(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`
}

export function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1)
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