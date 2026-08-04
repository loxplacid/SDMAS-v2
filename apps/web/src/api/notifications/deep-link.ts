/**
 * Safe deep-link resolution for notifications.
 *
 * Notifications may carry a navigation target in `data.route` (e.g. the
 * event payload embeds a route for the initiating user). We only trust
 * routes that match an explicit allowlist of internal app prefixes and
 * reject anything that could be an open redirect or unsafe URL scheme.
 */

const SAFE_ROUTE_PREFIXES = [
  '/students',
  '/dashboard',
  '/fees',
  '/attendance',
  '/academic',
  '/reports',
  '/report-cards',
  '/notifications',
  '/admissions',
  '/documents',
  '/risk',
  '/class',
  '/teacher',
  '/profile',
  '/workflow',
  '/leave',
  '/search',
  '/command-center',
] as const

function isSafeRoute(route: string): boolean {
  // Must be an internal absolute path.
  if (!route.startsWith('/') || route.startsWith('//')) return false
  // Reject anything that looks like a URL scheme / open redirect.
  if (/^[a-z]+:/i.test(route)) return false
  if (/[?#]/.test(route)) return false
  // Allowlist prefixes only.
  return SAFE_ROUTE_PREFIXES.some(
    (prefix) => route === prefix || route.startsWith(`${prefix}/`)
  )
}

/**
 * Return a validated navigation target from a notification's `data`, or
 * null when the notification has no (or an unsafe) route.
 */
export function getNotificationRoute(
  data: Record<string, unknown> | null | undefined,
): string | null {
  if (!data || typeof data.route !== 'string') return null
  const route = data.route.trim()
  if (!route || !isSafeRoute(route)) return null
  return route
}
