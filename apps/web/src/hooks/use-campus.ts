import { useState, useEffect } from 'react'
import { useAuth } from '../api/auth/auth-context'
import { institutionApi } from '../api/institution/institution-api'

const STORAGE_PREFIX = 'campus_cache_'

interface UseCampusReturn {
  campusName: string | null
  isLoading: boolean
}

function readCachedCampusName(campusId: number): string | null {
  try {
    return localStorage.getItem(`${STORAGE_PREFIX}${campusId}`)
  } catch {
    return null
  }
}

function writeCachedCampusName(campusId: number, name: string): void {
  try {
    localStorage.setItem(`${STORAGE_PREFIX}${campusId}`, name)
  } catch {
    // Silently ignore storage quota errors
  }
}

function clearCachedCampusName(campusId: number): void {
  try {
    localStorage.removeItem(`${STORAGE_PREFIX}${campusId}`)
  } catch {
    // Silently ignore
  }
}

/**
 * Fetch the campus/organization name for the current user's campus.
 *
 * Uses the user's ``campus_id`` from the auth context to look up the
 * campus record via ``GET /api/institution/campuses/{id}``.
 *
 * Results are cached in ``localStorage`` (keyed by campus ID) so that
 * subsequent page loads display the name instantly without a loading flash.
 *
 * Returns ``{ campusName, isLoading }`` where ``campusName`` is ``null``
 * when the user has no campus assigned or the fetch hasn't completed.
 */
export function useCampus(): UseCampusReturn {
  const { user } = useAuth()
  const campusId = user?.campus_id

  // Initialise from cache when campus_id is known
  const [campusName, setCampusName] = useState<string | null>(
    campusId ? readCachedCampusName(campusId) : null,
  )
  const [isLoading, setIsLoading] = useState(
    campusId ? readCachedCampusName(campusId) === null : false,
  )

  useEffect(() => {
    const id = user?.campus_id

    if (!id) {
      setCampusName(null)
      setIsLoading(false)
      return
    }

    // Hydrate from cache if we haven't already
    const cached = readCachedCampusName(id)
    if (cached !== null) {
      setCampusName(cached)
      setIsLoading(false)
      return
    }

    let cancelled = false
    setIsLoading(true)

    institutionApi.getCampus(id)
      .then((campus) => {
        if (!cancelled) {
          writeCachedCampusName(id, campus.name)
          setCampusName(campus.name)
          setIsLoading(false)
        }
      })
      .catch(() => {
        if (!cancelled) {
          clearCachedCampusName(id)
          setCampusName(null)
          setIsLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [user?.campus_id])

  return { campusName, isLoading }
}
