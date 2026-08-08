/**
 * Glint §5/§10 — the milestone registry.
 *
 * The product's L4 celebration allow-list. A moment is a milestone only if
 * the registry owns it; pages call `celebrate(milestoneId, ctx)` after a
 * successful mutation and the registry decides whether the moment is due
 * (quota, once-per-campus) and persists the firing. Pages never invent
 * celebrations, and no milestone fires more than its quota allows.
 *
 * Storage family matches `use-nav-persistence` (`sdmas::*`), scoped per
 * campus so a school's milestones are its own.
 */

export type DelightLevel = 'L1' | 'L2' | 'L3' | 'L4' | 'L5'

export interface MilestoneContext {
  /** Campus scope — the milestone bookkeeping key. */
  campusId?: number | string | null
  /** School-year scope (L5 quota cadence). Optional; defaults to campus. */
  schoolYear?: string
  /** Anything the caption needs: entity name, count, etc. */
  [key: string]: unknown
}

export interface Milestone {
  id: string
  level: DelightLevel
  /** Maximum firings per campus (per school-year when `schoolYear` is set). */
  quota: number
  /** Fire at most once per campus, ever. First-of-kind moments. */
  once: boolean
  /** The celebration copy. Receives the context passed by the caller. */
  label: (ctx: MilestoneContext) => string
  caption: (ctx: MilestoneContext) => string
}

export const MILESTONES: readonly Milestone[] = [
  {
    id: 'first-student',
    level: 'L4',
    quota: 1,
    once: true,
    label: (ctx) => 'First student enrolled',
    caption: (ctx) =>
      `You're building ${typeof ctx.campusName === 'string' && ctx.campusName ? ctx.campusName + "'s" : "your school's"} directory.`,
  },
  {
    id: 'first-teacher',
    level: 'L4',
    quota: 1,
    once: true,
    label: () => 'First teacher added',
    caption: (ctx) => 'Teaching staff can now be assigned to classes and subjects.',
  },
  {
    id: 'first-class',
    level: 'L4',
    quota: 1,
    once: true,
    label: () => 'First class created',
    caption: (ctx) => 'The academic structure of your school is taking shape.',
  },
  {
    id: 'first-term',
    level: 'L4',
    quota: 1,
    once: true,
    label: () => 'First term opened',
    caption: (ctx) => 'Attendance, grades, and fees now have a home.',
  },
  {
    id: 'first-payment',
    level: 'L4',
    quota: 1,
    once: true,
    label: () => 'First payment recorded',
    caption: (ctx) => 'Collections are live. Fee tracking begins.',
  },
] as const

export const MILESTONE_MAP: ReadonlyMap<string, Milestone> = new Map(
  MILESTONES.map((m) => [m.id, m])
)

/* ------------------------------------------------------------------ */
/* Persistence — quota bookkeeping, campus-scoped                      */
/* ------------------------------------------------------------------ */

const STORAGE_PREFIX = 'sdmas::milestones::'

export interface MilestoneState {
  /** milestoneId → count of firings in the current scope. */
  counts: Record<string, number>
}

function readState(scopeKey: string): MilestoneState {
  try {
    const raw = localStorage.getItem(`${STORAGE_PREFIX}${scopeKey}`)
    if (!raw) return { counts: {} }
    const parsed = JSON.parse(raw) as MilestoneState
    return { counts: parsed.counts ?? {} }
  } catch {
    return { counts: {} }
  }
}

function writeState(scopeKey: string, state: MilestoneState): void {
  try {
    localStorage.setItem(`${STORAGE_PREFIX}${scopeKey}`, JSON.stringify(state))
  } catch {
    // Storage unavailable/quota — milestone still fires this session.
  }
}

/** Build the scope key: campus (required), plus school-year when provided. */
export function milestoneScopeKey(ctx: MilestoneContext): string {
  const campus = ctx.campusId ?? 'global'
  return ctx.schoolYear ? `${campus}::${ctx.schoolYear}` : String(campus)
}

/**
 * Is the milestone due in this scope — and record it atomically?
 * Returns true (and persists the firing) only if the quota allows. Safe to
 * call optimistically; repeated calls after the quota is exhausted no-op.
 */
export function tryFireMilestone(milestone: Milestone, ctx: MilestoneContext): boolean {
  const scopeKey = milestoneScopeKey(ctx)
  const state = readState(scopeKey)
  const fired = state.counts[milestone.id] ?? 0

  if (milestone.once && fired >= 1) return false
  if (fired >= milestone.quota) return false

  writeState(scopeKey, {
    counts: { ...state.counts, [milestone.id]: fired + 1 },
  })
  return true
}

/** Pure read for tests/telemetry — does not mutate. */
export function milestoneCount(milestoneId: string, ctx: MilestoneContext): number {
  return readState(milestoneScopeKey(ctx)).counts[milestoneId] ?? 0
}
