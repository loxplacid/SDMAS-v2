const { IDatabase } = require('../interfaces');

class Database extends IDatabase {
  constructor() {
    super();
    this.connection = null;
    this.inTransaction = false;
    this.schemaInitialized = false;
    this._storage = {};
    this._preTransactionStorage = undefined;
  }

  /**
   * Connect to the database
   */
  connect() {
    if (this.isConnected()) {
      throw new Error('Already connected to database');
    }
    // Simulate database connection
    this.connection = { status: 'connected' };
    this.inTransaction = false;
    console.log('Database connected');
  }

  /**
   * Disconnect from the database
   */
  disconnect() {
    if (this.inTransaction) {
      try {
        this.rollback();
      } catch (rollbackError) {
        console.error('Rollback failed during disconnect:', rollbackError);
      }
    }
    if (this.connection) {
      this.connection.status = 'disconnected';
    }
    this.connection = null;
    this.inTransaction = false;
    this.schemaInitialized = false;
    console.log('Database disconnected');
  }

  /**
   * Checks if database is currently connected
   * @returns {boolean} True if connected, false otherwise
   */
  isConnected() {
    return Boolean(this.connection && this.connection.status === 'connected');
  }

  /**
   * Checks if database schema has been initialized
   * @returns {boolean} True if initialized, false otherwise
   */
  isSchemaInitialized() {
    return this.schemaInitialized;
  }

  /**
   * Safely initializes database schema statements atomically.
   * If any statement fails, all changes are rolled back.
   * @param {Array<string>} schemaStatements - Array of SQL statements to initialize schema
   * @throws {Error} If not connected, invalid input, or execution fails
   */
  initializeSchema(schemaStatements) {
    if (!this.isConnected()) {
      throw new Error('Not connected to database');
    }

    if (!Array.isArray(schemaStatements) || schemaStatements.length === 0) {
      throw new Error('Schema statements must be a non-empty array of SQL strings');
    }

    this.transaction((db) => {
      for (const statement of schemaStatements) {
        db.query(statement);
      }
    });

    this.schemaInitialized = true;
  }

  /**
   * Begins a database transaction
   */
  beginTransaction() {
    if (!this.isConnected()) {
      throw new Error('Not connected to database');
    }
    if (this.inTransaction) {
      throw new Error('Transaction is already in progress');
    }
    this.inTransaction = true;
    this._preTransactionStorage = this._deepClone(this._storage);
    console.log('Transaction started');
  }

  /**
   * Commits the current database transaction
   */
  commit() {
    if (!this.isConnected()) {
      throw new Error('Not connected to database');
    }
    if (!this.inTransaction) {
      throw new Error('No active transaction to commit');
    }
    this.inTransaction = false;
    this._preTransactionStorage = undefined;
    console.log('Transaction committed');
  }

  /**
   * Rolls back the current database transaction
   */
  rollback() {
    if (!this.isConnected()) {
      throw new Error('Not connected to database');
    }
    if (!this.inTransaction) {
      throw new Error('No active transaction to roll back');
    }
    if (this._preTransactionStorage !== undefined) {
      this._storage = this._preTransactionStorage;
      this._preTransactionStorage = undefined;
    }
    this.inTransaction = false;
    console.log('Transaction rolled back');
  }

  /**
   * Executes a callback within an atomic transaction block.
   * Automatically commits on success or rolls back on error.
   * @param {Function} callback - Function to execute inside transaction
   * @returns {*} Result of the callback
   */
  transaction(callback) {
    if (typeof callback !== 'function') {
      throw new Error('Transaction callback must be a function');
    }

    this.beginTransaction();
    try {
      const result = callback(this);
      this.commit();
      return result;
    } catch (error) {
      try {
        this.rollback();
      } catch (rollbackError) {
        console.error('Rollback failed:', rollbackError);
      } finally {
        this.inTransaction = false;
      }
      throw error;
    }
  }

  /**
   * Executes a database query
   * @param {string} sql - SQL query string
   * @param {Array} [params=[]] - Query parameters
   * @returns {Object} Query result object
   * @throws {Error} If not connected or query is invalid
   */
  query(sql, params = []) {
    if (!this.isConnected()) {
      throw new Error('Not connected to database');
    }

    if (!sql || typeof sql !== 'string' || sql.trim().length === 0) {
      throw new Error('Invalid SQL query provided');
    }

    if (!Array.isArray(params)) {
      throw new Error('Query params must be an array');
    }
    
    // Simulate query execution
    console.log(`Executing: ${sql} with params:`, params);

    return this._executeQuery(sql, params);
  }

  _deepClone(obj) {
    if (obj === null || typeof obj !== 'object') return obj;
    if (Array.isArray(obj)) return obj.map(v => this._deepClone(v));
    const result = {};
    for (const key of Object.keys(obj)) {
      result[key] = this._deepClone(obj[key]);
    }
    return result;
  }

  _executeQuery(sql, params = []) {
    const trimmed = sql.trim();

    const createMatch = trimmed.match(/^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)/i);
    if (createMatch) {
      const tableName = createMatch[1];
      if (!this._storage[tableName]) {
        this._storage[tableName] = { rows: [] };
      }
      return { rows: [], affectedRows: 0 };
    }

    const insertMatch = trimmed.match(/^\s*INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)/i);
    if (insertMatch) {
      const tableName = insertMatch[1];
      const columns = insertMatch[2].split(',').map(c => c.trim());
      if (!this._storage[tableName]) {
        this._storage[tableName] = { rows: [] };
      }
      const row = {};
      let paramIndex = 0;
      for (const col of columns) {
        row[col] = params[paramIndex++];
      }
      const existingIds = this._storage[tableName].rows.map(r => r.id).filter(id => id != null);
      row.id = existingIds.length > 0 ? Math.max(...existingIds) + 1 : 1;
      this._storage[tableName].rows.push(row);
      return { rows: [], affectedRows: 1, insertId: row.id };
    }

    const selectMatch = trimmed.match(/^\s*SELECT\s+(.+?)\s+FROM\s+(\w+)(?:\s+WHERE\s+(.+?))?(?:\s+ORDER\s+BY\s+.+)?$/i);
    if (selectMatch) {
      const tableName = selectMatch[2];
      const whereClause = selectMatch[3];
      if (!this._storage[tableName]) {
        return { rows: [], affectedRows: 0 };
      }
      let rows = [...this._storage[tableName].rows];
      if (whereClause) {
        rows = this._applyWhere(rows, whereClause, params);
      }
      return { rows, affectedRows: rows.length };
    }

    const updateMatch = trimmed.match(/^\s*UPDATE\s+(\w+)\s+SET\s+(.+?)(?:\s+WHERE\s+(.+))?$/i);
    if (updateMatch) {
      const tableName = updateMatch[1];
      const setClause = updateMatch[2];
      const whereClause = updateMatch[3];
      if (!this._storage[tableName]) {
        return { rows: [], affectedRows: 0 };
      }
      const setAssignments = setClause.split(',').map(s => {
        const m = s.trim().match(/^(\w+)\s*=\s*\?$/);
        return m ? m[1].toLowerCase() : null;
      }).filter(Boolean);

      let targetRows = [...this._storage[tableName].rows];
      if (whereClause) {
        targetRows = this._applyWhere(targetRows, whereClause, params.slice(setAssignments.length));
      }

      let affectedCount = 0;
      for (const targetRow of targetRows) {
        const idx = this._storage[tableName].rows.indexOf(targetRow);
        if (idx !== -1) {
          setAssignments.forEach((col, i) => {
            this._storage[tableName].rows[idx][col] = params[i];
          });
          affectedCount++;
        }
      }
      return { rows: [], affectedRows: affectedCount };
    }

    const deleteMatch = trimmed.match(/^\s*DELETE\s+FROM\s+(\w+)(?:\s+WHERE\s+(.+))?$/i);
    if (deleteMatch) {
      const tableName = deleteMatch[1];
      const whereClause = deleteMatch[2];
      if (!this._storage[tableName]) {
        return { rows: [], affectedRows: 0 };
      }
      if (whereClause) {
        const toDelete = this._applyWhere([...this._storage[tableName].rows], whereClause, params);
        const before = this._storage[tableName].rows.length;
        for (const row of toDelete) {
          const idx = this._storage[tableName].rows.indexOf(row);
          if (idx !== -1) {
            this._storage[tableName].rows.splice(idx, 1);
          }
        }
        return { rows: [], affectedRows: before - this._storage[tableName].rows.length };
      }
      const count = this._storage[tableName].rows.length;
      this._storage[tableName].rows = [];
      return { rows: [], affectedRows: count };
    }

    return { rows: [], affectedRows: 0 };
  }

  _applyWhere(rows, whereClause, params) {
    let paramIndex = 0;
    const conditions = whereClause.split(/\s+AND\s+/i);
    for (const condition of conditions) {
      const lookup = condition.trim();
      let match;
      match = lookup.match(/^(\w+)\s*(<=|>=|<|>|!=|=)\s*\?$/);
      if (match) {
        const col = match[1];
        const op = match[2];
        const expected = params[paramIndex++];
        rows = rows.filter(row => {
          const val = row[col];
          if (op === '=') return val === expected;
          if (op === '!=') return val !== expected;
          if (val == null || expected == null) return false;
          if (op === '<') return val < expected;
          if (op === '>') return val > expected;
          if (op === '<=') return val <= expected;
          if (op === '>=') return val >= expected;
          return true;
        });
        continue;
      }
      match = lookup.match(/^(\w+)\s+LIKE\s+\?$/i);
      if (match) {
        const col = match[1];
        const pattern = String(params[paramIndex++]);
        const regex = new RegExp('^' + pattern.replace(/%/g, '.*').replace(/_/g, '.') + '$', 'i');
        rows = rows.filter(row => regex.test(String(row[col])));
        continue;
      }
      paramIndex++;
    }
    return rows;
  }
}

module.exports = Database;
