import { api } from '../client/http-client'
import type { Page } from '../generated/types'

/**
 * Admin Dashboard API — fetches summary data from existing backend endpoints.
 *
 * Each endpoint returns a Page response; we request size=1 to get the total
 * count without downloading all records. This is the cheapest way to get
 * system-wide metrics from the existing API surface.
 */

export interface AdminOverview {
  users: EntityCount
  students: EntityCount
  teachers: EntityCount
  classes: EntityCount
  sections: EntityCount
  enrollments: EntityCount
  attendance_records: EntityCount
  fee_dues: EntityCount
  payments: EntityCount
  fee_types: EntityCount
  audit_events: EntityCount
  notifications: EntityCount
  leave_requests: EntityCount
  admissions: EntityCount
  generated_at: string
}

export interface EntityCount {
  total: number
}

async function getCount<T>(path: string, params?: Record<string, string | number | boolean | undefined | null>): Promise<number> {
  try {
    const result = await api.get<Page<T>>(path, { size: 1, ...params } as Record<string, string | number | boolean | undefined | null>)
    return result.total
  } catch {
    return 0
  }
}

export const adminDashboardApi = {
  getOverview: async (): Promise<AdminOverview> => {
    const [
      users,
      students,
      teachers,
      classes,
      sections,
      enrollments,
      attendance_records,
      fee_dues,
      payments,
      fee_types,
      audit_events,
      notifications,
      leave_requests,
      admissions,
    ] = await Promise.all([
      getCount<any>('/admin/users'),
      getCount<any>('/students'),
      getCount<any>('/teachers'),
      getCount<any>('/classes'),
      getCount<any>('/sections'),
      getCount<any>('/enrollments'),
      getCount<any>('/attendance'),
      getCount<any>('/fees/dues'),
      getCount<any>('/fees/payments'),
      getCount<any>('/fees/fee-types'),
      getCount<any>('/audit'),
      getCount<any>('/notifications'),
      getCount<any>('/leave'),
      getCount<any>('/admissions/applications'),
    ])

    return {
      users: { total: users },
      students: { total: students },
      teachers: { total: teachers },
      classes: { total: classes },
      sections: { total: sections },
      enrollments: { total: enrollments },
      attendance_records: { total: attendance_records },
      fee_dues: { total: fee_dues },
      payments: { total: payments },
      fee_types: { total: fee_types },
      audit_events: { total: audit_events },
      notifications: { total: notifications },
      leave_requests: { total: leave_requests },
      admissions: { total: admissions },
      generated_at: new Date().toISOString(),
    }
  },

  getUserCounts: async (): Promise<{ active: number; inactive: number; by_role: Record<string, number> }> => {
    const roles = ['admin', 'principal', 'accountant', 'staff', 'teacher', 'student', 'parent']
    const [active, inactive, ...roleCounts] = await Promise.all([
      getCount<any>('/admin/users', { is_active: true }),
      getCount<any>('/admin/users', { is_active: false }),
      ...roles.map((r) => getCount<any>('/admin/users', { role: r })),
    ])

    const by_role: Record<string, number> = {}
    roles.forEach((r, i) => { by_role[r] = roleCounts[i] })

    return { active, inactive, by_role }
  },
}
