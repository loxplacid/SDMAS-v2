/**
 * Ambient declaration for the official sqlite3-worker1.mjs worker entry,
 * served as a static asset (see vite.config.ts sqliteWasmAssets plugin).
 * The package ships this file without type declarations.
 */
declare module '/sqlite3-worker1.mjs' {
  export interface SqliteWorkerPromiser {
    (type: string, args?: unknown): Promise<any>
    v2?: (config?: unknown) => Promise<SqliteWorkerPromiser>
  }
  export const sqlite3Worker1Promiser: SqliteWorkerPromiser
}
