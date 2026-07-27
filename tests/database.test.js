const Database = require('../implementations/database');

describe('Database Implementation', () => {
  let db;

  beforeEach(() => {
    db = new Database();
  });

  test('should initially be disconnected', () => {
    expect(db.isConnected()).toBe(false);
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
});
