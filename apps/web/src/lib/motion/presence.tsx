/**
 * P7 — MotionPresence: the app's AnimatePresence wrapper.
 *
 * The single place where mount/unmount choreography is configured for
 * transient UI — drawers, modals, dropdowns, popovers, contextual panels.
 * Defaults to `mode="wait"` so the outgoing surface finishes before the
 * incoming one starts (the pattern dialogs/panels want; no overlap).
 * `popLayout` can be passed for list reflows where exiting items should
 * pop out of flow immediately.
 *
 * Exiting children should expose an `exit` frame — use `MotionReveal` or a
 * motion component with an `exit` prop.
 */

import { AnimatePresence } from 'motion/react'
import type { AnimatePresenceProps } from 'motion/react'
import type { ReactNode } from 'react'

export interface MotionPresenceProps extends AnimatePresenceProps {
  children?: ReactNode
}

export function MotionPresence({ mode = 'wait', ...props }: MotionPresenceProps) {
  return <AnimatePresence mode={mode} {...props} />
}
