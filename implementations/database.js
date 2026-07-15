const { IDatabase } = require('../interfaces');

class Database extends IDatabase {
  constructor() {
    super();
    this.connection = null;
  }

  connect() {
    // Simulate database connection
    this.connection = { status: 'connected' };
    console.log('Database connected');
  }

  disconnect() {
    this.connection = null;
    console.log('Database disconnected');
  }

  query(sql, params) {
    if (!this.connection) {
      throw new Error('Not connected to database');
    }
    
    // Simulate query execution
    console.log(`Executing: ${sql} with params:`, params);
    return { rows: [], affectedRows: 0 };
  }
}

module.exports = Database;
