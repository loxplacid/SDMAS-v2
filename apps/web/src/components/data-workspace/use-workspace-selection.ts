import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'

/**
 * P9 — Workspace selection: the single "current" entity of a list workspace
 * (what the inspector previews), synchronized with the URL as a search param.
 *
 *  - `open(id)` pushes a history entry (`?<param>=<id>`) so browser
 *    back/forward navigate between selections, refreshes preserve the
 *    selection, and the URL is deep-linkable;
 *  - `close()` pushes the entry without the param — the workspace returns to
 *    the plain list;
 *  - the param is validated as a positive integer; anything else reads as
 *    "no selection".
 *
 * This is deliberately separate from bulk checkbox selection
 * (`useWorkspace.selection`): bulk operations select many rows, the
 * inspector previews one.
 */

function parseId(raw: string | null): string | null {
  if (raw === null) return null
  const n = Number(raw)
  return Number.isInteger(n) && n > 0 ? String(n) : null
}

export interface UseWorkspaceSelectionResult {
  /** The selected entity id (stringified), or null when nothing is selected. */
  selectedId: string | null
  /** Convenience — `selectedId !== null`. */
  isOpen: boolean
  /** Select an entity and push history so back/forward step through selections. */
  open: (id: string | number) => void
  /** Clear the selection (removes the param, pushes history). */
  close: () => void
}

export function useWorkspaceSelection(paramKey: string): UseWorkspaceSelectionResult {
  const [searchParams, setSearchParams] = useSearchParams()

  const selectedId = parseId(searchParams.get(paramKey))

  const open = useCallback(
    (id: string | number) => {
      // Only valid ids may enter the URL, and re-selecting the current row
      // must not stack a duplicate history entry — back would appear to
      // "do nothing". Guard before navigating (react-router still pushes
      // when the updater returns the same params).
      const value = parseId(String(id))
      if (value === null || value === selectedId) return
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.set(paramKey, value)
          return next
        },
        { replace: false }
      )
    },
    [paramKey, selectedId, setSearchParams]
  )

  const close = useCallback(() => {
    // Nothing selected — nothing to remove; don't touch the history stack.
    if (selectedId === null) return
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete(paramKey)
        return next
      },
      { replace: false }
    )
  }, [paramKey, selectedId, setSearchParams])

  return {
    selectedId,
    isOpen: selectedId !== null,
    open,
    close,
  }
}
