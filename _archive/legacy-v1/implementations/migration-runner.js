class MigrationRunner {
  constructor(database) {
    if (!database) {
      throw new Error('Database is required');
    }
    this.database = database;
    this._migrations = [];
  }

  register(migration) {
    if (!migration || typeof migration.version !== 'number' ||
        !migration.name || typeof migration.name !== 'string' ||
        typeof migration.up !== 'function') {
      throw new Error('Migration must have version (number), name (string), and up (function)');
    }
    if (!Number.isInteger(migration.version) || migration.version < 1) {
      throw new Error('Migration version must be a positive integer');
    }
    if (this._migrations.some(m => m.version === migration.version)) {
      throw new Error(`Migration version ${migration.version} is already registered`);
    }
    this._migrations.push(migration);
  }

  getRegisteredMigrations() {
    return [...this._migrations].sort((a, b) => a.version - b.version);
  }

  _ensureMetaTable() {
    this.database.query(
      'CREATE TABLE IF NOT EXISTS _migrations (version INT PRIMARY KEY, name VARCHAR(255), appliedAt VARCHAR(50))'
    );
  }

  getAppliedMigrations() {
    const result = this.database.query('SELECT * FROM _migrations ORDER BY version ASC');
    return result.rows;
  }

  getPendingMigrations() {
    const applied = this.getAppliedMigrations();
    const appliedVersions = new Set(applied.map(m => m.version));
    return this._migrations
      .filter(m => !appliedVersions.has(m.version))
      .sort((a, b) => a.version - b.version);
  }

  run() {
    this._ensureMetaTable();
    const pending = this.getPendingMigrations();
    const results = [];

    for (const migration of pending) {
      this.database.transaction((db) => {
        migration.up(db);
        db.query('INSERT INTO _migrations (version, name, appliedAt) VALUES (?, ?, ?)', [
          migration.version,
          migration.name,
          new Date().toISOString()
        ]);
      });
      results.push({ version: migration.version, name: migration.name, status: 'applied' });
    }

    return results;
  }
}

module.exports = MigrationRunner;
