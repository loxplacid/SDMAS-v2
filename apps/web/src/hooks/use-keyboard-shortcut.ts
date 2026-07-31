import { useEffect, useRef, useCallback } from 'react'

type KeyMap = Record<string, (e: KeyboardEvent) => void>

export function useKeyboardShortcut(keymap: KeyMap, deps: any[] = []) {
  const keymapRef = useRef(keymap)
  keymapRef.current = keymap

  const handler = useCallback(
    (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.tagName === 'SELECT' ||
        target.isContentEditable
      ) {
        if (e.key !== '/' || target.tagName !== 'INPUT') {
          return
        }
      }

      for (const [keyCombo, callback] of Object.entries(keymapRef.current)) {
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
    deps,
  )

  useEffect(() => {
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [handler])
}
