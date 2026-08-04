const Database = require('../implementations/database');
const MigrationRunner = require('../implementations/migration-runner');

describe('MigrationRunner', () => {
  let db;
  let runner;

  beforeEach(() => {
    db = new Database();
    db.connect();
    runner = new MigrationRunner(db);
  });

  describe('constructor validation', () => {
    test('should reject when database is not provided', () => {
      expect(() => new MigrationRunner()).toThrow('Database is required');
      expect(() => new MigrationRunner(null)).toThrow('Database is required');
    });
  });

  describe('register migration', () => {
    test('should register a valid migration', () => {
      runner.register({
        version: 1,
        name: 'create users table',
        up: jest.fn()
      });
      const registered = runner.getRegisteredMigrations();
      expect(registered).toHaveLength(1);
      expect(registered[0].version).toBe(1);
      expect(registered[0].name).toBe('create users table');
    });

    test('should reject migration without version', () => {
      expect(() => {
        runner.register({ name: 'test', up: jest.fn() });
      }).toThrow('Migration must have version');
    });

    test('should reject migration with non-integer version', () => {
      expect(() => {
        runner.register({ version: 1.5, name: 'test', up: jest.fn() });
      }).toThrow('positive integer');
    });

    test('should reject migration with version less than 1', () => {
      expect(() => {
        runner.register({ version: 0, name: 'test', up: jest.fn() });
      }).toThrow('positive integer');
    });

    test('should reject migration without name', () => {
      expect(() => {
        runner.register({ version: 1, name: 123, up: jest.fn() });
      }).toThrow('Migration must have version');
    });

    test('should reject migration without up function', () => {
      expect(() => {
        runner.register({ version: 1, name: 'test' });
      }).toThrow('Migration must have version');
    });

    test('should reject duplicate migration version', () => {
      runner.register({ version: 1, name: 'first', up: jest.fn() });
      expect(() => {
        runner.register({ version: 1, name: 'duplicate', up: jest.fn() });
      }).toThrow('Migration version 1 is already registered');
    });

    test('should return sorted registered migrations by version', () => {
      runner.register({ version: 3, name: 'third', up: jest.fn() });
      runner.register({ version: 1, name: 'first', up: jest.fn() });
      runner.register({ version: 2, name: 'second', up: jest.fn() });

      const registered = runner.getRegisteredMigrations();
      expect(registered.map(m => m.version)).toEqual([1, 2, 3]);
    });
  });

  describe('migration state queries', () => {
    test('should return empty applied migrations on fresh database', () => {
      const applied = runner.getAppliedMigrations();
      expect(applied).toEqual([]);
    });

    test('should return empty pending migrations on fresh database', () => {
      const pending = runner.getPendingMigrations();
      expect(pending).toEqual([]);
    });

    test('should report pending migrations after registration', () => {
      runner.register({ version: 1, name: 'v1', up: jest.fn() });
      runner.register({ version: 5, name: 'v5', up: jest.fn() });

      const pending = runner.getPendingMigrations();
      expect(pending).toHaveLength(2);
      expect(pending[0].version).toBe(1);
      expect(pending[1].version).toBe(5);
    });

    test('should show no pending after migrations are applied', () => {
      runner.register({ version: 1, name: 'v1', up: jest.fn() });
      runner.run();
      const pending = runner.getPendingMigrations();
      expect(pending).toEqual([]);
    });
  });

  describe('migration execution', () => {
    test('should create meta table and run a migration', () => {
      const up = jest.fn();
      runner.register({ version: 1, name: 'create users', up });

      const spy = jest.spyOn(db, 'query');
      const results = runner.run();

      expect(results).toHaveLength(1);
      expect(results[0].version).toBe(1);
      expect(results[0].name).toBe('create users');
      expect(results[0].status).toBe('applied');
      expect(up).toHaveBeenCalledTimes(1);
      expect(up).toHaveBeenCalledWith(db);
      spy.mockRestore();
    });

    test('should execute migration up function with database instance', () => {
      let capturedDb;
      runner.register({
        version: 1,
        name: 'create users',
        up: (database) => { capturedDb = database; }
      });

      runner.run();
      expect(capturedDb).toBe(db);
    });

    test('should record migration to meta table after success', () => {
      runner.register({ version: 1, name: 'test migration', up: jest.fn() });
      runner.run();

      const applied = runner.getAppliedMigrations();
      expect(applied).toHaveLength(1);
      expect(applied[0].version).toBe(1);
      expect(applied[0].name).toBe('test migration');
      expect(applied[0].appliedAt).toBeDefined();
      expect(typeof applied[0].appliedAt).toBe('string');
    });
  });

  describe('idempotency', () => {
    test('should not re-apply already applied migrations', () => {
      const up = jest.fn();
      runner.register({ version: 1, name: 'v1', up });

      runner.run();

      expect(up).toHaveBeenCalledTimes(1);

      const secondRun = runner.run();
      expect(secondRun).toHaveLength(0);
      expect(up).toHaveBeenCalledTimes(1);
    });

    test('should only apply new migrations on subsequent runs', () => {
      runner.register({ version: 1, name: 'v1', up: jest.fn() });
      runner.run();

      runner.register({ version: 2, name: 'v2', up: jest.fn() });

      const secondRun = runner.run();
      expect(secondRun).toHaveLength(1);
      expect(secondRun[0].version).toBe(2);
    });

    test('should be idempotent across multiple runs', () => {
      runner.register({ version: 1, name: 'v1', up: jest.fn() });
      runner.register({ version: 2, name: 'v2', up: jest.fn() });

      runner.run();
      runner.run();
      runner.run();

      const applied = runner.getAppliedMigrations();
      expect(applied).toHaveLength(2);
    });
  });

  describe('migration ordering', () => {
    test('should apply migrations in version order', () => {
      const order = [];
      runner.register({
        version: 2,
        name: 'second',
        up: jest.fn(() => order.push(2))
      });
      runner.register({
        version: 1,
        name: 'first',
        up: jest.fn(() => order.push(1))
      });
      runner.register({
        version: 3,
        name: 'third',
        up: jest.fn(() => order.push(3))
      });

      runner.run();
      expect(order).toEqual([1, 2, 3]);
    });
  });

  describe('migration failure handling', () => {
    test('should throw error when a migration fails', () => {
      runner.register({ version: 1, name: 'good', up: jest.fn() });
      runner.register({
        version: 2,
        name: 'bad',
        up: () => { throw new Error('Migration failed'); }
      });

      expect(() => runner.run()).toThrow('Migration failed');
    });

    test('should not record a failed migration', () => {
      runner.register({ version: 1, name: 'good', up: jest.fn() });
      runner.register({
        version: 2,
        name: 'bad',
        up: () => { throw new Error('Migration failed'); }
      });

      expect(() => runner.run()).toThrow();

      const applied = runner.getAppliedMigrations();
      expect(applied).toHaveLength(1);
      expect(applied[0].version).toBe(1);
    });

    test('should keep state consistent after a migration failure', () => {
      runner.register({ version: 1, name: 'good', up: jest.fn() });
      runner.register({
        version: 2,
        name: 'bad',
        up: () => { throw new Error('Migration failed'); }
      });
      runner.register({ version: 3, name: 'also good', up: jest.fn() });

      expect(() => runner.run()).toThrow();

      const applied = runner.getAppliedMigrations();
      expect(applied).toHaveLength(1);

      const pending = runner.getPendingMigrations();
      expect(pending).toHaveLength(2);
      expect(pending[0].version).toBe(2);
      expect(pending[1].version).toBe(3);
    });

    test('should allow fixing and re-running after failure', () => {
      runner.register({ version: 1, name: 'good', up: jest.fn() });

      let fail = true;
      runner.register({
        version: 2,
        name: 'bad then fixed',
        up: () => {
          if (fail) throw new Error('Migration failed');
        }
      });

      expect(() => runner.run()).toThrow();

      fail = false;

      const retry = runner.run();
      expect(retry).toHaveLength(1);
      expect(retry[0].version).toBe(2);
      expect(retry[0].status).toBe('applied');

      const applied = runner.getAppliedMigrations();
      expect(applied).toHaveLength(2);
    });
  });

  describe('transaction behavior', () => {
    test('should wrap migration and recording in a transaction', () => {
      const transactionSpy = jest.spyOn(db, 'transaction');
      runner.register({ version: 1, name: 'v1', up: jest.fn() });
      runner.run();

      expect(transactionSpy).toHaveBeenCalled();
      transactionSpy.mockRestore();
    });

    test('should roll back if migration throws and not record it', () => {
      const rollbackSpy = jest.spyOn(db, 'rollback');
      runner.register({
        version: 1,
        name: 'failing',
        up: () => { throw new Error('fail'); }
      });

      expect(() => runner.run()).toThrow();
      expect(rollbackSpy).toHaveBeenCalled();

      const applied = runner.getAppliedMigrations();
      expect(applied).toHaveLength(0);
      rollbackSpy.mockRestore();
    });
  });

  describe('existing database functionality', () => {
    test('should not break normal query execution', () => {
      const result = db.query('SELECT * FROM users WHERE id = ?', [1]);
      expect(result).toEqual({ rows: [], affectedRows: 0 });
    });

    test('should not break transactions', () => {
      const result = db.transaction((database) => {
        database.query('INSERT INTO items (name) VALUES (?)', ['test']);
        return 'ok';
      });
      expect(result).toBe('ok');
      expect(db.inTransaction).toBe(false);
    });

    test('should not break schema initialization', () => {
      db.initializeSchema(['CREATE TABLE test (id INT)']);
      expect(db.isSchemaInitialized()).toBe(true);
    });

    test('should coexist with repository operations', () => {
      runner.register({ version: 1, name: 'create items', up: jest.fn() });
      runner.run();

      const querySpy = jest.spyOn(db, 'query').mockReturnValue({
        rows: [],
        affectedRows: 1,
        insertId: 42
      });

      const Repository = require('../implementations/repository');
      const repo = new Repository(db);
      const saved = repo.save({ name: 'test', description: 'test' });
      expect(saved.id).toBe(42);

      querySpy.mockRestore();
    });
  });
});
