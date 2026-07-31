import { useState, useCallback, useEffect, useRef } from 'react'
import { parentApi } from '../api/parent/parent-api'
import type { LinkedChild } from '../api/parent/parent-api'

/**
 * Hook to manage parent-child links via the backend API.
 * Parents can link to student records so only their children's data appears.
 * The parent MUST have the 'parent' role to use this.
 */
export function useParentChildren() {
  const [linkedIds, setLinkedIds] = useState<number[]>([])
  const [children, setChildren] = useState<LinkedChild[]>([])
  const [loading, setLoading] = useState(true)
  const fetchIdRef = useRef(0)

  // Fetch linked children from the API on mount
  useEffect(() => {
    const fetchId = ++fetchIdRef.current
    setLoading(true)
    parentApi.listChildren()
      .then((kids) => {
        if (fetchId === fetchIdRef.current) {
          setChildren(kids)
          setLinkedIds(kids.map((k) => k.id))
          setLoading(false)
        }
      })
      .catch(() => {
        // If not authenticated as parent, set empty
        if (fetchId === fetchIdRef.current) {
          setChildren([])
          setLinkedIds([])
          setLoading(false)
        }
      })
  }, [])

  const linkStudent = useCallback(async (studentId: number) => {
    try {
      await parentApi.linkChild(studentId)
      // Refresh the children list
      const kids = await parentApi.listChildren()
      setChildren(kids)
      setLinkedIds(kids.map((k) => k.id))
    } catch {
      // Error handled by the caller
      throw new Error('Failed to link child')
    }
  }, [])

  const unlinkStudent = useCallback(async (studentId: number) => {
    try {
      await parentApi.unlinkChild(studentId)
      setChildren((prev) => prev.filter((c) => c.id !== studentId))
      setLinkedIds((prev) => prev.filter((id) => id !== studentId))
    } catch {
      throw new Error('Failed to unlink child')
    }
  }, [])

  const isLinked = useCallback(
    (studentId: number) => linkedIds.includes(studentId),
    [linkedIds],
  )

  const linkMultiple = useCallback(async (studentIds: number[]) => {
    try {
      for (const id of studentIds) {
        await parentApi.linkChild(id)
      }
      // Refresh the children list
      const kids = await parentApi.listChildren()
      setChildren(kids)
      setLinkedIds(kids.map((k) => k.id))
    } catch {
      throw new Error('Failed to link some children')
    }
  }, [])

  return {
    /** Full linked child objects */
    children,
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
    /** Whether initial data is loading */
    loading,
  }
}
