/**
 * Universal search — ranking.
 *
 * Final rank = bm25 (text relevance) + recency boost + frequency boost.
 *
 *  - bm25 from SQLite FTS5 is negative and unbounded below; we clamp and
 *    normalise to [0,1] per query batch so it dominates but never drowns
 *    the other signals.
 *  - recency: entities touched recently get a small lift.
 *  - frequency: entities the user opens often get a lift (per-device).
 *
 * All functions are pure so the ranking logic is unit-testable.
 */

export interface RankableItem {
  id: string
  bm25: number
  /** ISO timestamp of last change (index `changed_at`). */
  changedAt?: string | null
}

export interface RankWeights {
  /** Recency half-life in days. */
  recencyHalfLifeDays?: number
  /** Max boost fraction applied to bm25 by recency. */
  recencyMaxBoost?: number
  /** Max boost fraction applied to bm25 by frequency. */
  frequencyMaxBoost?: number
}

const DEFAULT_WEIGHTS: Required<RankWeights> = {
  recencyHalfLifeDays: 30,
  recencyMaxBoost: 0.5,
  frequencyMaxBoost: 0.5,
}

/** Recency boost: exp(-age/halfLife), age in days, clamped to [0,1]. */
export function recencyBoost(
  changedAt: string | null | undefined,
  weights: RankWeights = {},
): number {
  const { recencyHalfLifeDays, recencyMaxBoost } = {
    ...DEFAULT_WEIGHTS,
    ...weights,
  }
  if (!changedAt) return 0
  const ageMs = Date.now() - new Date(changedAt).getTime()
  if (Number.isNaN(ageMs) || ageMs < 0) return 0
  const ageDays = ageMs / 86_400_000
  return Math.min(1, Math.exp(-ageDays / recencyHalfLifeDays)) * recencyMaxBoost
}

/**
 * Frequency boost from the per-device usage log. `openCount` is the number
 * of times the user opened this entity; rank = log2(1+count) mapped to
 * [0, frequencyMaxBoost].
 */
export function frequencyBoost(
  openCount: number,
  weights: RankWeights = {},
): number {
  const { frequencyMaxBoost } = { ...DEFAULT_WEIGHTS, ...weights }
  if (openCount <= 0) return 0
  return Math.min(1, Math.log2(1 + openCount) / 5) * frequencyMaxBoost
}

/** Combine the three signals into a final rank. */
export function combinedRank(
  item: RankableItem,
  openCount: number,
  weights: RankWeights = {},
): number {
  const bm25 = clamp01(normaliseBm25(item.bm25))
  const recency = recencyBoost(item.changedAt, weights)
  const frequency = frequencyBoost(openCount, weights)
  return clamp01(bm25 + recency + frequency)
}

/** Map unbounded negative bm25 to [0,1]. SQLite bm25 is typically -1..-6. */
export function normaliseBm25(bm25: number): number {
  // bm25 <= -8 → 0; bm25 >= 0 → 1; linear in between.
  return clamp01((bm25 + 8) / 8)
}

export function clamp01(n: number): number {
  if (Number.isNaN(n)) return 0
  return Math.max(0, Math.min(1, n))
}

// ---------------------------------------------------------------------------
// Per-device usage log (frequency + recency of opens)
// ---------------------------------------------------------------------------

export interface UsageEntry {
  /** Composite id (entity_type-entity_id). */
  id: string
  count: number
  lastOpenedAt: number
}

const USAGE_KEY = 'sdmas:search:usage'

function readUsage(): Record<string, UsageEntry> {
  try {
    const raw = localStorage.getItem(USAGE_KEY)
    if (!raw) return {}
    return JSON.parse(raw) as Record<string, UsageEntry>
  } catch {
    return {}
  }
}

function writeUsage(usage: Record<string, UsageEntry>): void {
  try {
    localStorage.setItem(USAGE_KEY, JSON.stringify(usage))
  } catch {
    // localStorage full/unavailable — degrade silently.
  }
}

/** Record that the user opened an entity (called on selection). */
export function recordOpen(id: string): void {
  const usage = readUsage()
  const now = Date.now()
  const prev = usage[id]
  usage[id] = {
    id,
    count: (prev?.count ?? 0) + 1,
    lastOpenedAt: now,
  }
  // Cap the store at 500 entries (LRU-ish by lastOpenedAt) to keep it lean.
  const keys = Object.keys(usage)
  if (keys.length > 500) {
    const sorted = keys.sort(
      (a, b) => usage[a].lastOpenedAt - usage[b].lastOpenedAt,
    )
    for (const k of sorted.slice(0, keys.length - 500)) delete usage[k]
  }
  writeUsage(usage)
}

/** Open count for a set of ids (used by the ranking pass). */
export function readOpenCounts(ids: string[]): Record<string, number> {
  if (ids.length === 0) return {}
  const usage = readUsage()
  const out: Record<string, number> = {}
  for (const id of ids) out[id] = usage[id]?.count ?? 0
  return out
}
