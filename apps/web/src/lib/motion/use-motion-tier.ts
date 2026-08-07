import { useEffect, useState } from 'react'
import { getMotionTier, type MotionTier } from './tokens'

/**
 * ONE shared environment subscription for every `useMotionTier` consumer
 * (spec §8). A single MutationObserver + media listener serves the whole
 * app — the sidebar alone mounts dozens of `useMove` instances (each nav
 * item, each rail label), and a per-hook observer would fan that out into
 * dozens of DOM observers all watching the same attribute.
 *
 * The subscription lives for the module lifetime: one observer watching
 * `data-motion-tier` on <html> is negligible, and it is torn down when the
 * page unloads. Consumers subscribe/unsubscribe their own notifier only.
 */

/** Notifiers registered by mounted `useMotionTier` hooks. */
const tierSubscribers = new Set<() => void>()

let environmentSubscribed = false
let sharedObserver: MutationObserver | undefined

function subscribeToEnvironment(): void {
  if (environmentSubscribed || typeof window === 'undefined') return
  environmentSubscribed = true

  const notifyAll = () => tierSubscribers.forEach((notify) => notify())

  // In-app "Reduce motion" toggle flips data-motion-tier on <html>.
  if (typeof MutationObserver !== 'undefined') {
    sharedObserver = new MutationObserver(notifyAll)
    sharedObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-motion-tier'],
    })
  }

  // OS-level reduced-motion preference changes.
  window.matchMedia?.('(prefers-reduced-motion: reduce)')?.addEventListener('change', notifyAll)
}

/**
 * Reactive motion tier (spec §7, §8).
 *
 * Resolves the active tier from the environment and re-renders when it
 * changes:
 *  - `prefers-reduced-motion: reduce` media queries
 *  - the `data-motion-tier` attribute on <html> (in-app "Reduce motion"
 *    toggle), observed via a single shared MutationObserver
 *
 * Components never branch on media queries themselves — they consume the
 * tier from this hook (or `getMotionTier` for one-shot reads).
 */
export function useMotionTier(): MotionTier {
  const [tier, setTier] = useState<MotionTier>(getMotionTier)

  useEffect(() => {
    const notify = () => setTier(getMotionTier())
    tierSubscribers.add(notify)
    subscribeToEnvironment()
    return () => {
      tierSubscribers.delete(notify)
    }
  }, [])

  return tier
}
