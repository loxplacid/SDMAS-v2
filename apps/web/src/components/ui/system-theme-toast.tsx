import { useEffect } from 'react'
import { useToast } from './toast'

const STORAGE_KEY = 'sdmas-theme'

function hasStoredTheme(): boolean {
  try {
    return STORAGE_KEY in localStorage
  } catch {
    return false
  }
}

/**
 * Listens for OS-level theme changes and shows a toast notification.
 * Only fires when the user has NOT explicitly set a theme preference.
 */
export function SystemThemeToast() {
  const { showToast } = useToast()

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')

    const handler = (e: MediaQueryListEvent) => {
      // Only show toast if user hasn't explicitly set a preference
      if (hasStoredTheme()) return

      const isDark = e.matches
      const label = isDark ? 'Dark mode' : 'Light mode'
      const icon = isDark ? '🌙' : '☀️'

      showToast(`${icon} System theme changed to ${label}`, 'info', 'Theme Updated')
    }

    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [showToast])

  // No UI to render — this component only shows toasts
  return null
}
