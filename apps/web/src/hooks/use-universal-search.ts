import { useState, useEffect, useCallback, useRef } from 'react'
import * as db from '../lib/search/search-db'
import { buildMatchQuery } from '../lib/search/query-pipeline'
import { combinedRank, readOpenCounts } from '../lib/search/ranking'
import { runIndexSync } from '../lib/search/sync'
import type { SearchResultItem, GroupedSearchResult } from '../api/search/search-api'

export interface UniversalSearchResult {
  query: string
  total: number
  tookMs: number
  results: SearchResultItem[]
  grouped: GroupedSearchResult[]
  mode: 'fts' | 'like' | 'none'
}

export interface UniversalSearchStatus {
  ready: boolean
  inProgress: boolean
  error: string | null
  lastSyncedAt: number | null
}

/** Status shape used by the sync orchestrator. */
export type IndexSyncStatusShape = {
  inProgress: boolean
  error: string | null
  lastSyncedAt: number | null
}

const GROUP_LABELS: Record<string, string> = {
  student: 'Students',
  teacher: 'Teachers',
  class: 'Classes',
  section: 'Sections',
  subject: 'Subjects',
  fee: 'Fees',
  payment: 'Payments',
  receipt: 'Receipts',
  notification: 'Notifications',
  document: 'Documents',
  attendance: 'Attendance',
  grade_record: 'Exam Marks',
  leave_request: 'Leave',
  admission_application: 'Admissions',
}

const GROUP_ICONS: Record<string, string> = {
  student: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197',
  teacher: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
  class: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
  section: 'M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm0 8a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6z',
  subject: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253',
  fee: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1',
  payment: 'M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z',
  receipt: 'M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l2-1 2 1 2-1 2 1 2-1 2 1 2-1z',
  notification: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9',
  document: 'M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z',
  attendance: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2',
  grade_record: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
  leave_request: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
  admission_application: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
}

/** When the query is empty, fall back to recent/frequent usage signals. */
export function useUniversalSearch() {
  const [status, setStatus] = useState<UniversalSearchStatus>({
    ready: false,
    inProgress: false,
    error: null,
    lastSyncedAt: null,
  })
  const statusRef = useRef(status)
  statusRef.current = status

  // Background index sync: once on mount, then every 5 minutes while the
  // tab is visible. Idempotent and never blocks the main thread (all DB work
  // happens in the sqlite worker).
  useEffect(() => {
    let cancelled = false
    const kick = async () => {
      if (cancelled) return
      await runIndexSync(statusRef.current as IndexSyncStatusShape)
      setStatus({ ...statusRef.current })
    }
    void kick()
    const interval = window.setInterval(() => {
      if (document.visibilityState === 'visible') void kick()
    }, 5 * 60_000)
    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [])

  const search = useCallback(
    async (query: string): Promise<UniversalSearchResult> => {
      const started = performance.now()
      const trimmed = query.trim()
      if (!trimmed) {
        return { query, total: 0, tookMs: 0, results: [], grouped: [], mode: 'none' }
      }

      // Warm the index lazily on first search so the very first keystroke
      // still resolves against whatever data is already synced.
      try {
        await db.openDatabase()
      } catch (err) {
        setStatus({
          ...statusRef.current,
          error: err instanceof Error ? err.message : String(err),
        })
        return { query, total: 0, tookMs: 0, results: [], grouped: [], mode: 'none' }
      }

      // Typo-correction vocabulary harvested from the local index.
      let vocabulary: string[] = []
      try {
        const sample = await db.exec(
          'SELECT search_text FROM entities LIMIT 500',
        )
        vocabulary = sample.map((r) => String(r.search_text))
      } catch {
        vocabulary = []
      }

      const matchQuery = buildMatchQuery(trimmed, { vocabulary })
      const likeQuery = trimmed

      let result
      try {
        result = await db.searchIndex(matchQuery, likeQuery)
      } catch (err) {
        setStatus({
          ...statusRef.current,
          error: err instanceof Error ? err.message : String(err),
        })
        return { query, total: 0, tookMs: 0, results: [], grouped: [], mode: 'none' }
      }

      if (result.hits.length === 0) {
        return {
          query,
          total: 0,
          tookMs: performance.now() - started,
          results: [],
          grouped: [],
          mode: 'none',
        }
      }

      const openCounts = readOpenCounts(result.hits.map((h) => h.id))
      const ranked = result.hits
        .map((hit) => ({
          ...hit,
          rank: combinedRank(hit, openCounts[hit.id] ?? 0),
        }))
        .sort((a, b) => b.rank - a.rank)
        .slice(0, 40)

      const results: SearchResultItem[] = ranked.map((r) => ({
        id: r.id,
        entity_type: r.entity_type,
        entity_id: r.entity_id,
        label: r.label,
        description: r.description,
        route: r.route,
        match_field: null,
        score: r.rank,
      }))

      const grouped = groupResults(results)

      return {
        query,
        total: results.length,
        tookMs: performance.now() - started,
        results,
        grouped,
        mode: result.mode,
      }
    },
    [],
  )

  return { search, status }
}

function groupResults(results: SearchResultItem[]): GroupedSearchResult[] {
  const order = [
    'student',
    'teacher',
    'class',
    'section',
    'subject',
    'fee',
    'payment',
    'receipt',
    'notification',
    'document',
    'attendance',
    'grade_record',
    'leave_request',
    'admission_application',
  ]
  const byType = new Map<string, SearchResultItem[]>()
  for (const r of results) {
    const arr = byType.get(r.entity_type) ?? []
    arr.push(r)
    byType.set(r.entity_type, arr)
  }
  const out: GroupedSearchResult[] = []
  for (const type of order) {
    const items = byType.get(type)
    if (items && items.length > 0) {
      out.push({
        entity_type: type,
        label: GROUP_LABELS[type] ?? type,
        icon: GROUP_ICONS[type] ?? '',
        items,
      })
    }
  }
  return out
}
