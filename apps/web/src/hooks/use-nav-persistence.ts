import { useState, useCallback, useEffect } from 'react'

const SIDEBAR_KEY = 'sdmas::sidebar-collapsed'
const RECENT_KEY = 'sdmas::recent-items'
const FAVORITES_KEY = 'sdmas::favorites'
const MAX_RECENT = 8

interface RecentItem {
  path: string
  label: string
  timestamp: number
}

export function useNavPersistence() {
  // ── Sidebar collapsed state ──
  const [sidebarCollapsed, setSidebarCollapsedState] = useState(() => {
    try {
      const stored = localStorage.getItem(SIDEBAR_KEY)
      return stored === 'true'
    } catch {
      return false
    }
  })

  const setSidebarCollapsed = useCallback((collapsed: boolean) => {
    setSidebarCollapsedState(collapsed)
    try {
      localStorage.setItem(SIDEBAR_KEY, String(collapsed))
    } catch { /* noop */ }
  }, [])

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsedState((prev) => {
      const next = !prev
      try { localStorage.setItem(SIDEBAR_KEY, String(next)) } catch { /* noop */ }
      return next
    })
  }, [])

  // ── Recent items ──
  const [recentItems, setRecentItems] = useState<RecentItem[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]')
    } catch {
      return []
    }
  })

  const addRecentItem = useCallback((path: string, label: string) => {
    setRecentItems((prev) => {
      const filtered = prev.filter((item) => item.path !== path)
      const updated = [{ path, label, timestamp: Date.now() }, ...filtered].slice(0, MAX_RECENT)
      try { localStorage.setItem(RECENT_KEY, JSON.stringify(updated)) } catch { /* noop */ }
      return updated
    })
  }, [])

  const clearRecentItems = useCallback(() => {
    setRecentItems([])
    try { localStorage.setItem(RECENT_KEY, '[]') } catch { /* noop */ }
  }, [])

  // ── Favorites ──
  const [favorites, setFavorites] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(FAVORITES_KEY) || '[]')
    } catch {
      return []
    }
  })

  const toggleFavorite = useCallback((path: string) => {
    setFavorites((prev) => {
      const updated = prev.includes(path)
        ? prev.filter((p) => p !== path)
        : [...prev, path]
      try { localStorage.setItem(FAVORITES_KEY, JSON.stringify(updated)) } catch { /* noop */ }
      return updated
    })
  }, [])

  const isFavorite = useCallback((path: string) => {
    return favorites.includes(path)
  }, [favorites])

  // Listen for custom events (sidebar toggle from other components)
  useEffect(() => {
    const handler = () => {
      setSidebarCollapsedState((prev) => {
        const next = !prev
        try { localStorage.setItem(SIDEBAR_KEY, String(next)) } catch { /* noop */ }
        return next
      })
    }
    window.addEventListener('sdmas:toggle-sidebar', handler)
    return () => window.removeEventListener('sdmas:toggle-sidebar', handler)
  }, [])

  return {
    sidebarCollapsed,
    setSidebarCollapsed,
    toggleSidebar,
    recentItems,
    addRecentItem,
    clearRecentItems,
    favorites,
    toggleFavorite,
    isFavorite,
  }
}
