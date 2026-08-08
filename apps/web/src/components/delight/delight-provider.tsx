import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { useAuth } from '../../api/auth/auth-context'
import { AchievementToast } from './achievement-toast'
import { MILESTONE_MAP, tryFireMilestone, type MilestoneContext } from './registry'

/**
 * Glint §10 — the delight provider.
 *
 * One L4/L5 moment at a time (a second milestone replaces the first, never
 * stacks). Mounted at the app root next to `ToastProvider`; its toasts use
 * their own `role="status"` region so they never double-announce with L2
 * toasts. The campus scope comes from the auth user's `campus_id`.
 */

interface DelightContextValue {
  /**
   * Celebrate a registry milestone. No-op when the milestone isn't in the
   * registry or its quota is exhausted — pages call this after successful
   * mutations and let the registry decide.
   */
  celebrate: (milestoneId: string, ctx?: MilestoneContext) => void
}

const DelightContext = createContext<DelightContextValue | null>(null)

interface ActiveMilestone {
  id: string
  label: string
  caption: string
}

export function DelightProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const campusId = user?.campus_id ?? null
  const [active, setActive] = useState<ActiveMilestone | null>(null)

  const celebrate = useCallback(
    (milestoneId: string, ctx: MilestoneContext = {}) => {
      const milestone = MILESTONE_MAP.get(milestoneId)
      // L4-only for W3: L5 (confetti summits) arrives with the Confetti
      // component in W4 — the registry stays the single source of truth
      // so future L5 calls render through this same provider.
      if (!milestone || milestone.level !== 'L4') return

      const context: MilestoneContext = { ...ctx, campusId: ctx.campusId ?? campusId }
      if (!tryFireMilestone(milestone, context)) return

      // One at a time: a second milestone replaces the current toast.
      setActive({
        id: milestone.id,
        label: milestone.label(context),
        caption: milestone.caption(context),
      })
    },
    [campusId]
  )

  const dismiss = useCallback(() => setActive(null), [])

  const value = useMemo(() => ({ celebrate }), [celebrate])

  return (
    <DelightContext.Provider value={value}>
      {children}
      {active && (
        <div className="fixed bottom-5 right-5 z-[110] flex flex-col gap-2.5 max-w-sm w-full pointer-events-none">
          <AchievementToast key={active.id} label={active.label} caption={active.caption} onDismiss={dismiss} />
        </div>
      )}
    </DelightContext.Provider>
  )
}

export function useDelight(): DelightContextValue {
  const ctx = useContext(DelightContext)
  // Same contract as `useToast`: throws outside the provider. Tests that
  // render a wired page in isolation must wrap it in <DelightProvider />.
  if (!ctx) throw new Error('useDelight must be used within DelightProvider')
  return ctx
}
