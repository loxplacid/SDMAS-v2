import { useEffect, useCallback } from 'react'

type KeyMap = Record<string, (e: KeyboardEvent) => void>

/**
 * Registers global keyboard shortcuts via a keymap object.
 * Keys like 'k' trigger when that key is pressed.
 * Combine with ctrl/meta: 'mod+k' matches either Cmd (macOS) or Ctrl (Windows/Linux).
 * 
 * @example
 * useKeyboardShortcut({
 *   '/': () => searchRef.current?.focus(),
 *   'n': () => setModalOpen(true),
 *   'mod+s': (e) => { e.preventDefault(); handleSave() },
 * })
 */
export function useKeyboardShortcut(keymap: KeyMap, deps: any[] = []) {
  const handler = useCallback(
    (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      // Don't trigger shortcuts when typing in input/textarea/select
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.tagName === 'SELECT' ||
        target.isContentEditable
      ) {
        // Exception: allow '/' when NOT in a search/input field (to focus search)
        // Actually, '/' should also work from inputs... let's handle this case
        if (e.key !== '/' || target.tagName !== 'INPUT') {
          return
        }
      }

      for (const [keyCombo, callback] of Object.entries(keymap)) {
        const parts = keyCombo.split('+')
        const hasMod = parts.includes('mod')
        const hasCtrl = parts.includes('ctrl')
        const hasMeta = parts.includes('meta')
        const hasShift = parts.includes('shift')
        const key = parts[parts.length - 1]

        const modPressed = e.metaKey || e.ctrlKey
        const ctrlPressed = e.ctrlKey
        const metaPressed = e.metaKey
        const shiftPressed = e.shiftKey

        if (
          key === e.key.toLowerCase() &&
          (hasMod ? modPressed : !modPressed) &&
          (hasCtrl ? ctrlPressed : !ctrlPressed || hasMod) &&
          (hasMeta ? metaPressed : !metaPressed || hasMod) &&
          (hasShift ? shiftPressed : !shiftPressed)
        ) {
          callback(e)
          return
        }
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [keymap, ...deps]
  )

  useEffect(() => {
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [handler])
}
