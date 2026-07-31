import { useState, useEffect, useRef, useCallback } from 'react'
import { searchApi, type SearchResultItem, type GlobalSearchResponse, type SearchEntityType, type GroupedSearchResult } from '../api/search/search-api'

interface UseGlobalSearchOptions {
  debounceMs?: number
  minQueryLength?: number
}

export interface UseGlobalSearchReturn {
  query: string
  results: SearchResultItem[]
  grouped: GroupedSearchResult[]
  total: number
  loading: boolean
  error: string | null
  tookMs: number | null
  recentSearches: { query: string; count: number }[]
  frequentSearches: { query: string; count: number }[]
  setQuery: (q: string) => void
  search: (q: string, types?: SearchEntityType[]) => void
  clear: () => void
  loadRecent: () => Promise<void>
}

export function useGlobalSearch(
  options: UseGlobalSearchOptions = {},
): UseGlobalSearchReturn {
  const { debounceMs = 300, minQueryLength = 1 } = options

  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResultItem[]>([])
  const [grouped, setGrouped] = useState<GroupedSearchResult[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tookMs, setTookMs] = useState<number | null>(null)
  const [recentSearches, setRecentSearches] = useState<{ query: string; count: number }[]>([])
  const [frequentSearches, setFrequentSearches] = useState<{ query: string; count: number }[]>([])

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const search = useCallback(
    async (q: string, types?: SearchEntityType[]) => {
      if (!q || q.length < minQueryLength) {
        setResults([])
        setGrouped([])
        setTotal(0)
        setTookMs(null)
        return
      }

      if (abortRef.current) {
        abortRef.current.abort()
      }

      setLoading(true)
      setError(null)

      try {
        const response = await searchApi.global({
          query: q,
          types,
          page: 1,
          size: 20,
        })
        setResults(response.results)
        setGrouped(response.grouped)
        setTotal(response.total)
        setTookMs(response.took_ms)
      } catch (err: any) {
        if (err?.name === 'AbortError') return
        setError(err?.detail || err?.message || 'Search failed')
        setResults([])
        setGrouped([])
        setTotal(0)
      } finally {
        setLoading(false)
      }
    },
    [minQueryLength],
  )

  const debouncedSearch = useCallback(
    (q: string) => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
      }
      debounceRef.current = setTimeout(() => {
        search(q)
      }, debounceMs)
    },
    [search, debounceMs],
  )

  const handleSetQuery = useCallback(
    (q: string) => {
      setQuery(q)
      debouncedSearch(q)
    },
    [debouncedSearch],
  )

  const clear = useCallback(() => {
    setQuery('')
    setResults([])
    setGrouped([])
    setTotal(0)
    setError(null)
    setTookMs(null)
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }
  }, [])

  const loadRecent = useCallback(async () => {
    try {
      const [recent, frequent] = await Promise.all([
        searchApi.recent(10),
        searchApi.frequent(5),
      ])
      setRecentSearches(recent.map((r) => ({ query: r.query, count: r.result_count })))
      setFrequentSearches(frequent)
    } catch {
      // Silent fail
    }
  }, [])

  useEffect(() => {
    loadRecent()
  }, [loadRecent])

  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
      }
    }
  }, [])

  return {
    query,
    results,
    grouped,
    total,
    loading,
    error,
    tookMs,
    recentSearches,
    frequentSearches,
    setQuery: handleSetQuery,
    search,
    clear,
    loadRecent,
  }
}
