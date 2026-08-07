/**
 * Universal search — SQLite bridge.
 *
 * Wraps the official `@sqlite.org/sqlite-wasm` worker1 promiser (served from
 * `/sqlite3-worker1.mjs` via the Vite asset plugin). The worker keeps the
 * FTS5 index off the main thread, persisted to OPFS when available and
 * falling back to in-memory otherwise.
 *
 * The promiser's message protocol is promise-based (v2 API): each call
 * returns a Promise resolved with the worker's response object.
 */

export interface IndexRow {
  id: string
  entity_type: string
  entity_id: number
  label: string
  description: string | null
  route: string
  search_text: string
  changed_at: string | null
}

export interface SearchHit {
  id: string
  entity_type: string
  entity_id: number
  label: string
  description: string | null
  route: string
  bm25: number
}

export type SearchMode = 'fts' | 'like'

export interface SearchResult {
  mode: SearchMode
  hits: SearchHit[]
}

interface ExecResponse {
  columns?: string[]
  rows?: Record<string, unknown>[]
  message?: string
  error?: string
}

interface ExecArgs {
  sql: string
  rowMode?: 'object'
  bind?: Record<string, unknown>
}

/** Minimal structural type for the worker1 promiser. */
interface SqlitePromiser {
  (type: string, args?: unknown): Promise<any>
}

/** The package's promiser factory (v1 + v2 forms). */
interface SqlitePromiserFactory {
  (config?: unknown): SqlitePromiser
  v2?: (config?: unknown) => Promise<SqlitePromiser>
}

// ---------------------------------------------------------------------------
// Promiser bootstrap
// ---------------------------------------------------------------------------

let promiserPromise: Promise<SqlitePromiser> | null = null
let dbHandle: { id: string } | null = null

async function initPromiser(): Promise<SqlitePromiser> {
  if (promiserPromise) return promiserPromise

  // Lazy dynamic import: the sqlite engine (~1.2MB wasm) is only fetched on
  // first search/sync, never at app startup.
  promiserPromise = (async () => {
    const mod = (await import(
      '@sqlite.org/sqlite-wasm',
    )) as { sqlite3Worker1Promiser: SqlitePromiserFactory }
    const factory = mod.sqlite3Worker1Promiser
    if (!factory?.v2) {
      throw new Error('sqlite3 worker did not expose a promiser factory')
    }
    // `sqlite3-worker1.mjs` + `sqlite3.wasm` are served as static assets
    // (vite.config.ts sqliteWasmAssets plugin), so the worker never depends
    // on node_modules paths at runtime.
    const promiser = await factory.v2({
      worker: () => new Worker('/sqlite3-worker1.mjs', { type: 'module' }),
    })
    return promiser as SqlitePromiser
  })()

  try {
    return await promiserPromise
  } catch (err) {
    promiserPromise = null
    throw err
  }
}

/** Open the persistent index database (OPFS preferred). */
export async function openDatabase(): Promise<void> {
  const promiser = await initPromiser()
  if (dbHandle) return

  // OPFS persistence first; fall back to in-memory when unavailable.
  try {
    const res = await promiser('open', {
      filename: '/sdmas-search.db',
      vfs: 'opfs',
    })
    dbHandle = { id: res?.dbId }
  } catch {
    const res = await promiser('open', {
      filename: ':memory:',
    })
    dbHandle = { id: res?.dbId }
  }

  await exec(
    `CREATE TABLE IF NOT EXISTS entities (
       id TEXT PRIMARY KEY,
       entity_type TEXT NOT NULL,
       entity_id INTEGER NOT NULL,
       label TEXT NOT NULL,
       description TEXT,
       route TEXT NOT NULL,
       search_text TEXT NOT NULL,
       changed_at TEXT
     );
     CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
     CREATE INDEX IF NOT EXISTS idx_entities_changed ON entities(changed_at);
     CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);`,
  )
  await ensureFts()
}

/** (Re)create the FTS5 table if the schema is missing. */
async function ensureFts(): Promise<void> {
  try {
    await exec(`SELECT rowid FROM entities_fts LIMIT 1`)
  } catch {
    await exec(
      `CREATE VIRTUAL TABLE entities_fts USING fts5(
         entity_type, label, description, search_text,
         content='entities', content_rowid='rowid'
       );`,
    )
  }
}

/** Run one or more SQL statements; returns the last result set. */
export async function exec(
  sql: string,
  bind?: Record<string, unknown>,
): Promise<Record<string, unknown>[]> {
  const promiser = await initPromiser()
  if (!dbHandle) await openDatabase()

  const res = (await promiser('exec', {
    sql,
    rowMode: 'object',
    ...(bind ? { bind } : {}),
  } as ExecArgs)) as ExecResponse

  if (res.error) throw new Error(res.error)
  return res.rows ?? []
}

// ---------------------------------------------------------------------------
// Index operations
// ---------------------------------------------------------------------------

/** Replace the whole index with a fresh snapshot (full sync). */
export async function replaceIndex(rows: IndexRow[]): Promise<void> {
  await exec('DELETE FROM entities; DELETE FROM entities_fts;')
  await insertRows(rows)
}

/** Upsert rows into the index (incremental sync). */
export async function upsertRows(rows: IndexRow[]): Promise<void> {
  await insertRows(rows)
}

async function insertRows(rows: IndexRow[]): Promise<void> {
  if (rows.length === 0) return
  for (const row of rows) {
    // The FTS5 table is external-content (`content='entities'`), so its
    // rowid MUST mirror the entities table rowid or the join breaks.
    // Two-phase insert: insert/update content, fetch the rowid, then sync
    // the FTS entry with that explicit rowid.
    const params = {
      $id: row.id,
      $type: row.entity_type,
      $eid: row.entity_id,
      $label: row.label,
      $description: row.description ?? null,
      $route: row.route,
      $search: row.search_text,
      $changed: row.changed_at,
    }

    const existing = await exec('SELECT rowid FROM entities WHERE id = $id', {
      $id: row.id,
    })

    if (existing.length > 0) {
      // Update content, then rebuild the FTS entry for that rowid.
      const rowid = Number(existing[0].rowid)
      await exec(
        `UPDATE entities SET
           entity_type=$type, entity_id=$eid, label=$label, description=$description,
           route=$route, search_text=$search, changed_at=$changed
         WHERE id=$id;`,
        params,
      )
      await exec('DELETE FROM entities_fts WHERE rowid = $rowid', { $rowid: rowid })
      await exec(
        `INSERT INTO entities_fts (rowid, entity_type, label, description, search_text)
         VALUES ($rowid, $type, $label, $description, $search);`,
        { $rowid: rowid, ...params },
      )
    } else {
      // New row: insert content, fetch the fresh rowid, sync FTS.
      await exec(
        `INSERT INTO entities (id, entity_type, entity_id, label, description, route, search_text, changed_at)
         VALUES ($id, $type, $eid, $label, $description, $route, $search, $changed);`,
        params,
      )
      const inserted = await exec('SELECT rowid FROM entities WHERE id = $id', {
        $id: row.id,
      })
      const rowid = inserted.length > 0 ? Number(inserted[0].rowid) : null
      if (rowid != null) {
        await exec(
          `INSERT INTO entities_fts (rowid, entity_type, label, description, search_text)
           VALUES ($rowid, $type, $label, $description, $search);`,
          { $rowid: rowid, ...params },
        )
      }
    }
  }
}

/** Remove a row from the index (hard delete). */
export async function deleteRow(id: string): Promise<void> {
  const rows = await exec('SELECT rowid FROM entities WHERE id = $id', { $id: id })
  await exec('DELETE FROM entities WHERE id = $id', { $id: id })
  for (const r of rows) {
    await exec('DELETE FROM entities_fts WHERE rowid = $rowid', {
      $rowid: r.rowid,
    })
  }
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

const FTS_SELECT = `
  SELECT e.id, e.entity_type, e.entity_id, e.label, e.description, e.route,
         bm25(entities_fts, 5.0, 1.0, 1.0, 1.0) AS bm25
  FROM entities_fts
  JOIN entities e ON e.rowid = entities_fts.rowid
  WHERE entities_fts MATCH $query
  ORDER BY bm25
  LIMIT 40`

const LIKE_SELECT = `
  SELECT e.id, e.entity_type, e.entity_id, e.label, e.description, e.route, 0 AS bm25
  FROM entities e
  WHERE e.search_text LIKE $query OR e.label LIKE $query
  ORDER BY e.changed_at DESC
  LIMIT 40`

/**
 * Search the local index. Falls back from FTS5 to a LIKE scan when the
 * MATCH fails (typo, operator syntax, zero results).
 */
export async function searchIndex(
  matchQuery: string,
  likeQuery: string,
): Promise<SearchResult> {
  try {
    const rows = await exec(FTS_SELECT, { $query: matchQuery })
    if (rows.length > 0) {
      return {
        mode: 'fts',
        hits: rows.map((r) => toHit(r)),
      }
    }
  } catch {
    // FTS parse error (e.g. operator-only query) — fall through to LIKE.
  }
  const rows = await exec(LIKE_SELECT, { $query: `%${likeQuery}%` })
  return { mode: 'like', hits: rows.map((r) => toHit(r)) }
}

function toHit(r: Record<string, unknown>): SearchHit {
  return {
    id: String(r.id),
    entity_type: String(r.entity_type),
    entity_id: Number(r.entity_id),
    label: String(r.label),
    description: r.description != null ? String(r.description) : null,
    route: String(r.route),
    bm25: Number(r.bm25 ?? 0),
  }
}

// ---------------------------------------------------------------------------
// Sync metadata (per-device, persisted with the index)
// ---------------------------------------------------------------------------

export async function getMeta(key: string): Promise<string | null> {
  const rows = await exec('SELECT value FROM meta WHERE key = $key', { $key: key })
  return rows.length > 0 ? String(rows[0].value) : null
}

export async function setMeta(key: string, value: string): Promise<void> {
  await exec(
    `INSERT INTO meta (key, value) VALUES ($key, $value)
     ON CONFLICT(key) DO UPDATE SET value = excluded.value;`,
    { $key: key, $value: value },
  )
}

/** All entity types currently present in the local index. */
export async function indexEntityTypes(): Promise<string[]> {
  const rows = await exec('SELECT DISTINCT entity_type FROM entities')
  return rows.map((r) => String(r.entity_type))
}

/** Reset the index (permission or schema change). */
export async function clearIndex(): Promise<void> {
  await exec('DELETE FROM entities; DELETE FROM entities_fts; DELETE FROM meta;')
}

/** Close the database and release the worker. */
export async function closeDatabase(): Promise<void> {
  if (!dbHandle) return
  const promiser = await initPromiser()
  try {
    await promiser('close', { dbId: dbHandle.id })
  } catch {
    // Best-effort close.
  }
  dbHandle = null
  promiserPromise = null
}
