const Database = require('../implementations/database');

describe('Database Implementation', () => {
  let db;

  beforeEach(() => {
    db = new Database();
  });

  test('should initially be disconnected', () => {
    expect(db.isConnected()).toBe(false);
    expect(db.isSchemaInitialized()).toBe(false);
  });

  test('should throw error when executing query without connecting', () => {
    expect(() => {
      db.query('SELECT 1');
    }).toThrow('Not connected to database');
  });

  test('should successfully execute query when connected', () => {
    db.connect();
    expect(db.isConnected()).toBe(true);

    const result = db.query('SELECT * FROM users WHERE id = ?', [1]);
    expect(result).toEqual({ rows: [], affectedRows: 0 });
  });

  test('should throw error if connection status becomes disconnected', () => {
    db.connect();
    expect(db.isConnected()).toBe(true);

    db.disconnect();
    expect(db.isConnected()).toBe(false);

    expect(() => {
      db.query('SELECT 1');
    }).toThrow('Not connected to database');
  });

  test('should throw error when query SQL is empty or invalid', () => {
    db.connect();

    expect(() => {
      db.query('');
    }).toThrow('Invalid SQL query provided');

    expect(() => {
      db.query(null);
    }).toThrow('Invalid SQL query provided');
  });

  test('should handle transactions and commit on success', () => {
    db.connect();

    const result = db.transaction((database) => {
      database.query('INSERT INTO items (name) VALUES (?)', ['item1']);
      return 'success';
    });

    expect(result).toBe('success');
    expect(db.inTransaction).toBe(false);
  });

  test('should automatically roll back transaction on error and rethrow', () => {
    db.connect();

    expect(() => {
      db.transaction((database) => {
        database.query('INSERT INTO items (name) VALUES (?)', ['item1']);
        throw new Error('Database write failed');
      });
    }).toThrow('Database write failed');

    expect(db.inTransaction).toBe(false);
  });

  test('should throw error if nested or duplicate transaction is started', () => {
    db.connect();
    db.beginTransaction();

    expect(() => {
      db.beginTransaction();
    }).toThrow('Transaction is already in progress');

    db.rollback();
  });

  test('should initialize schema atomically', () => {
    db.connect();
    const schemaSqls = [
      'CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(100));',
      'CREATE TABLE items (id INT PRIMARY KEY, title VARCHAR(100));'
    ];

    db.initializeSchema(schemaSqls);
    expect(db.isSchemaInitialized()).toBe(true);
  });

  test('should roll back and keep schemaInitialized false if schema statement fails', () => {
    db.connect();
    const schemaSqls = [
      'CREATE TABLE users (id INT PRIMARY KEY);',
      '' // invalid query
    ];

    expect(() => {
      db.initializeSchema(schemaSqls);
    }).toThrow('Invalid SQL query provided');

    expect(db.isSchemaInitialized()).toBe(false);
    expect(db.inTransaction).toBe(false);
  });

  test('should throw error if initializeSchema is called without connection or with invalid statements', () => {
    expect(() => {
      db.initializeSchema(['CREATE TABLE test (id INT);']);
    }).toThrow('Not connected to database');

    db.connect();

    expect(() => {
      db.initializeSchema([]);
    }).toThrow('Schema statements must be a non-empty array of SQL strings');

    expect(() => {
      db.initializeSchema('CREATE TABLE test (id INT);');
    }).toThrow('Schema statements must be a non-empty array of SQL strings');
  });
});
