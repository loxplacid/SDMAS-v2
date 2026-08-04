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

  test('should throw error when connecting while already connected', () => {
    db.connect();
    expect(db.isConnected()).toBe(true);

    expect(() => {
      db.connect();
    }).toThrow('Already connected to database');

    expect(db.isConnected()).toBe(true);
  });

  test('should allow reconnecting after disconnecting', () => {
    db.connect();
    db.disconnect();
    expect(db.isConnected()).toBe(false);

    db.connect();
    expect(db.isConnected()).toBe(true);
  });

  test('should rollback active transaction when disconnect is called', () => {
    db.connect();
    const rollbackSpy = jest.spyOn(db, 'rollback');
    db.beginTransaction();
    db.disconnect();
    expect(rollbackSpy).toHaveBeenCalled();
    expect(db.isConnected()).toBe(false);
    expect(db.inTransaction).toBe(false);
  });

  test('should not attempt rollback when disconnecting without active transaction', () => {
    db.connect();
    const rollbackSpy = jest.spyOn(db, 'rollback');
    db.disconnect();
    expect(rollbackSpy).not.toHaveBeenCalled();
    expect(db.isConnected()).toBe(false);
    expect(db.inTransaction).toBe(false);
  });

  test('should still disconnect even if rollback fails', () => {
    db.connect();
    jest.spyOn(db, 'rollback').mockImplementation(() => {
      throw new Error('Rollback infrastructure failure');
    });
    db.beginTransaction();
    expect(() => {
      db.disconnect();
    }).not.toThrow();
    expect(db.isConnected()).toBe(false);
    expect(db.inTransaction).toBe(false);
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

  test('should throw error when query params is not an array', () => {
    db.connect();

    expect(() => {
      db.query('SELECT 1', null);
    }).toThrow('Query params must be an array');

    expect(() => {
      db.query('SELECT 1', 'not-an-array');
    }).toThrow('Query params must be an array');

    expect(() => {
      db.query('SELECT 1', { key: 'value' });
    }).toThrow('Query params must be an array');
  });

  test('should accept array params', () => {
    db.connect();

    expect(() => {
      db.query('SELECT 1', []);
    }).not.toThrow();

    expect(() => {
      db.query('SELECT 1', [1, 'two', { three: 3 }]);
    }).not.toThrow();
  });

  test('should accept query without explicit params (default empty array)', () => {
    db.connect();

    expect(() => {
      db.query('SELECT 1');
    }).not.toThrow();
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

    const afterRollback = db.query('SELECT * FROM items');
    expect(afterRollback.rows).toHaveLength(0);
  });

  test('should preserve original error when rollback itself fails', () => {
    db.connect();

    jest.spyOn(db, 'rollback').mockImplementation(() => {
      throw new Error('Rollback infrastructure failure');
    });

    expect(() => {
      db.transaction((database) => {
        throw new Error('Original query failure');
      });
    }).toThrow('Original query failure');

    expect(db.rollback).toHaveBeenCalled();
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

    const result = db.query('SELECT * FROM users');
    expect(result.rows).toHaveLength(0);
  });

  describe('Transaction data consistency', () => {
    beforeEach(() => {
      db.connect();
      db.query('CREATE TABLE txn_test (id INT, name VARCHAR(50))');
      db.query('INSERT INTO txn_test (id, name) VALUES (?, ?)', [1, 'original']);
    });

    test('transaction rollback should undo INSERT', () => {
      expect(() => {
        db.transaction((d) => {
          d.query('INSERT INTO txn_test (id, name) VALUES (?, ?)', [2, 'should-undo']);
          throw new Error('abort');
        });
      }).toThrow('abort');

      const rows = db.query('SELECT * FROM txn_test').rows;
      expect(rows).toHaveLength(1);
      expect(rows[0].id).toBe(1);
      expect(rows[0].name).toBe('original');
    });

    test('transaction commit should persist INSERT', () => {
      db.transaction((d) => {
        d.query('INSERT INTO txn_test (id, name) VALUES (?, ?)', [2, 'persisted']);
      });

      const rows = db.query('SELECT * FROM txn_test').rows;
      expect(rows).toHaveLength(2);
      expect(rows.find(r => r.id === 2).name).toBe('persisted');
    });

    test('transaction rollback should undo UPDATE', () => {
      expect(() => {
        db.transaction((d) => {
          d.query('UPDATE txn_test SET name = ? WHERE id = ?', ['updated', 1]);
          throw new Error('abort');
        });
      }).toThrow('abort');

      const rows = db.query('SELECT * FROM txn_test').rows;
      expect(rows).toHaveLength(1);
      expect(rows[0].name).toBe('original');
    });

    test('transaction rollback should undo DELETE', () => {
      db.query('INSERT INTO txn_test (id, name) VALUES (?, ?)', [2, 'to-delete']);

      expect(() => {
        db.transaction((d) => {
          d.query('DELETE FROM txn_test WHERE id = ?', [2]);
          throw new Error('abort');
        });
      }).toThrow('abort');

      const rows = db.query('SELECT * FROM txn_test').rows;
      expect(rows).toHaveLength(2);
    });
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

  describe('WHERE != operator', () => {
    beforeEach(() => {
      db.connect();
      db.query('CREATE TABLE test_items (id INT, name VARCHAR(50), status VARCHAR(20))');
      db.query('INSERT INTO test_items (id, name, status) VALUES (?, ?, ?)', [1, 'alpha', 'active']);
      db.query('INSERT INTO test_items (id, name, status) VALUES (?, ?, ?)', [2, 'beta', 'inactive']);
      db.query('INSERT INTO test_items (id, name, status) VALUES (?, ?, ?)', [3, 'gamma', 'active']);
    });

    test('SELECT with != should exclude matching rows', () => {
      const result = db.query('SELECT * FROM test_items WHERE status != ?', ['inactive']);
      expect(result.rows).toHaveLength(2);
      expect(result.rows.map(r => r.name).sort()).toEqual(['alpha', 'gamma']);
    });

    test('SELECT with != combined with AND should work', () => {
      const result = db.query('SELECT * FROM test_items WHERE id != ? AND status = ?', [1, 'active']);
      expect(result.rows).toHaveLength(1);
      expect(result.rows[0].name).toBe('gamma');
    });

    test('UPDATE with != should only update non-matching rows', () => {
      db.query('UPDATE test_items SET status = ? WHERE id != ?', ['archived', 1]);
      const result = db.query('SELECT * FROM test_items WHERE status = ?', ['archived']);
      expect(result.rows).toHaveLength(2);
      expect(result.rows.map(r => r.id).sort()).toEqual([2, 3]);
    });

    test('DELETE with != should only delete non-matching rows', () => {
      db.query('DELETE FROM test_items WHERE id != ?', [1]);
      const remaining = db.query('SELECT * FROM test_items');
      expect(remaining.rows).toHaveLength(1);
      expect(remaining.rows[0].id).toBe(1);
    });
  });
});
