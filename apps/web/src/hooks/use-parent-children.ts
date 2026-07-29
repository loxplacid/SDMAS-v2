import { useState, useCallback, useEffect } from 'react'

const STORAGE_KEY = 'sdmas-parent-children'

/**
 * Hook to manage parent-child links in localStorage.
 * Parents can link to student records so only their children's data appears.
 */
export function useParentChildren() {
  const [linkedIds, setLinkedIds] = useState<number[]>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        return Array.isArray(parsed) ? parsed : []
      }
    } catch {
      // ignore parse errors
    }
    return []
  })

  // Persist to localStorage on changes
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(linkedIds))
    } catch {
      // ignore storage errors
    }
  }, [linkedIds])

  const linkStudent = useCallback((studentId: number) => {
    setLinkedIds((prev) => {
      if (prev.includes(studentId)) return prev
      return [...prev, studentId]
    })
  }, [])

  const unlinkStudent = useCallback((studentId: number) => {
    setLinkedIds((prev) => prev.filter((id) => id !== studentId))
  }, [])

  const isLinked = useCallback(
    (studentId: number) => linkedIds.includes(studentId),
    [linkedIds],
  )

  const linkMultiple = useCallback((studentIds: number[]) => {
    setLinkedIds((prev) => {
      const merged = [...prev]
      for (const id of studentIds) {
        if (!merged.includes(id)) merged.push(id)
      }
      return merged
    })
  }, [])

  return {
    /** Array of linked student IDs */
    linkedIds,
    /** Link a student by ID */
    linkStudent,
    /** Unlink a student by ID */
    unlinkStudent,
    /** Check if a student is already linked */
    isLinked,
    /** Link multiple students at once */
    linkMultiple,
    /** Number of linked children */
    count: linkedIds.length,
  }
}
