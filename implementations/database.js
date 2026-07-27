const { IDatabase } = require('../interfaces');

class Database extends IDatabase {
  constructor() {
    super();
    this.connection = null;
    this.inTransaction = false;
    this.schemaInitialized = false;
  }

  /**
   * Connect to the database
   */
  connect() {
    // Simulate database connection
    this.connection = { status: 'connected' };
    this.inTransaction = false;
    console.log('Database connected');
  }

  /**
   * Disconnect from the database
   */
  disconnect() {
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

    for (const sql of schemaStatements) {
      if (!sql || typeof sql !== 'string' || sql.trim().length === 0) {
        throw new Error('Invalid SQL statement in schema initialization');
      }
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
      this.rollback();
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
    
    // Simulate query execution
    console.log(`Executing: ${sql} with params:`, params);
    return { rows: [], affectedRows: 0 };
  }
}

module.exports = Database;
