/**
 * Universal search — background sync orchestrator.
 *
 * Pulls permission-scoped entity batches from the backend (`/api/search/
 * index/sync`) and applies them to the local FTS5 index in a worker. The
 * server enforces role permissions and campus scoping, so the local index
 * only ever contains what the user is allowed to see.
 *
 * Protocol:
 *  - first run: page 0 of every permitted type (newest-first, capped) so the
 *    index is immediately useful; deeper pages fill the rest in the background
 *  - later runs: pass the stored per-type cursor as `since` → incremental
 *  - when the schema version or the permitted-type set changes, rebuild
 */

import { searchApi } from '../../api/search/search-api'
import * as db from './search-db'

/** Bump this when the index schema or search code changes meaningfully. */
export const SEARCH_SCHEMA_VERSION = 1

const PAGE_SIZE = 200
const SCHEMA_KEY = 'schema_version'
const SYNCED_KEY = 'synced_types'
const CURSOR_PREFIX = 'cursor:'

/** Priority order for the first sync pass (highest-value types first). */
const TYPE_ORDER = [
  'student',
  'teacher',
  'class',
  'section',
  'subject',
  'fee',
  'payment',
  'receipt',
  'notification',
  'document',
  'attendance',
  'grade_record',
  'leave_request',
  'admission_application',
]

export interface IndexSyncStatus {
  inProgress: boolean
  error: string | null
  lastSyncedAt: number | null
}

export interface IndexBatchItem {
  id: string
  entity_type: string
  entity_id: number
  label: string
  description: string | null
  route: string
  search_text: string
  changed_at: string | null
}

async function loadTypes(): Promise<string[]> {
  const raw = await db.getMeta(SYNCED_KEY)
  return raw ? (JSON.parse(raw) as string[]) : []
}

async function saveTypes(types: string[]): Promise<void> {
  await db.setMeta(SYNCED_KEY, JSON.stringify(types))
}

/** True when the local schema is behind the code's schema version. */
async function schemaUpToDate(): Promise<boolean> {
  const stored = await db.getMeta(SCHEMA_KEY)
  return stored === String(SEARCH_SCHEMA_VERSION)
}

async function markSchema(): Promise<void> {
  await db.setMeta(SCHEMA_KEY, String(SEARCH_SCHEMA_VERSION))
}

function cursorKey(type: string): string {
  return `${CURSOR_PREFIX}${type}`
}

/**
 * One sync pass. Returns the types actually synced (permitted on the server).
 * Never throws — failures are surfaced in the status and retried later.
 */
export async function runIndexSync(
  status: { inProgress: boolean; error: string | null; lastSyncedAt: number | null },
): Promise<string[]> {
  status.inProgress = true
  status.error = null
  try {
    await db.openDatabase()

    // Schema drift → rebuild from scratch.
    if (!(await schemaUpToDate())) {
      await db.clearIndex()
      await saveTypes([])
      await markSchema()
    }

    const previouslySynced = await loadTypes()
    const syncedThisRun: string[] = []
    const seenTypes = new Set(previouslySynced)

    // First pass: fetch a capped page of every permitted type (in priority
    // order) so the index is immediately useful.
    for (const type of TYPE_ORDER) {
      if (seenTypes.has(type)) continue
      const batch = await fetchBatch(type, 0, undefined)
      if (batch.items.length === 0) {
        // Either not permitted or genuinely empty — record so we don't
        // re-request on every pass (the permission check is cheap server-side).
        syncedThisRun.push(type)
        seenTypes.add(type)
        continue
      }
      await db.upsertRows(batch.items)
      syncedThisRun.push(type)
      seenTypes.add(type)
      if (batch.has_more) {
        // Schedule the tail in the background (fire-and-forget).
        void drainTail(type, 1)
      }
    }

    // Incremental pass: pull changes since the last cursor for every type.
    for (const type of previouslySynced) {
      const cursor = await db.getMeta(cursorKey(type))
      const batch = await fetchBatch(type, 0, cursor ?? undefined)
      if (batch.items.length > 0) {
        await db.upsertRows(batch.items)
      }
      syncedThisRun.push(type)
      if (batch.has_more) void drainTail(type, 1)
    }

    await saveTypes([...syncedThisRun])
    status.lastSyncedAt = Date.now()
    return syncedThisRun
  } catch (err) {
    status.error = err instanceof Error ? err.message : String(err)
    return []
  } finally {
    status.inProgress = false
  }
}

/** Fetch one page of index rows for a type. */
async function fetchBatch(
  type: string,
  page: number,
  since: string | undefined,
): Promise<{ items: IndexBatchItem[]; has_more: boolean }> {
  const res = await searchApi.indexSync(type, page, PAGE_SIZE, since)
  // Track the cursor so incremental syncs only pull changes.
  if (res.items.length > 0) {
    const latest = res.items[res.items.length - 1].changed_at
    if (latest) await db.setMeta(cursorKey(type), latest)
  }
  return { items: res.items, has_more: res.has_more }
}

/** Drain remaining pages of a type after the first pass. */
async function drainTail(type: string, startPage: number): Promise<void> {
  let page = startPage
  for (;;) {
    const batch = await fetchBatch(type, page, undefined)
    if (batch.items.length === 0) break
    await db.upsertRows(batch.items)
    if (!batch.has_more) break
    page += 1
  }
}
