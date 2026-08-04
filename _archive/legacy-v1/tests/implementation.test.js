const setupDIContainer = require('../di-setup');

describe('Implementation Components', () => {
  let container;

  beforeEach(() => {
    container = setupDIContainer();
  });

  test('should properly initialize all components', () => {
    const config = container.resolve('configuration');
    expect(config).toBeDefined();
    
    const logger = container.resolve('logger');
    expect(logger).toBeDefined();
    
    const database = container.resolve('database');
    expect(database).toBeDefined();
    
    const repository = container.resolve('repository');
    expect(repository).toBeDefined();
    
    const service = container.resolve('service');
    expect(service).toBeDefined();
    
    const sessionManager = container.resolve('sessionManager');
    expect(sessionManager).toBeDefined();
    
    const securityManager = container.resolve('securityManager');
    expect(securityManager).toBeDefined();
    
    const themeManager = container.resolve('themeManager');
    expect(themeManager).toBeDefined();
    
    const aiManager = container.resolve('aiManager');
    expect(aiManager).toBeDefined();
    
    const eventBus = container.resolve('eventBus');
    expect(eventBus).toBeDefined();
  });

  test('should execute basic functionality of each component', () => {
    // Test configuration
    const config = container.resolve('configuration');
    config.set('testKey', 'testValue');
    expect(config.get('testKey')).toBe('testValue');

    // Test logger
    const logger = container.resolve('logger');
    expect(() => logger.info('Test message')).not.toThrow();

    // Test database (should connect)
    const database = container.resolve('database');
    expect(database.connection).toBeDefined();
    
    // Test service execution
    const service = container.resolve('service');
    const result = service.execute('Hello World', { test: true });
    expect(result.success).toBe(true);

    // Test session manager
    const sessionManager = container.resolve('sessionManager');
    const sessionId = sessionManager.createSession('user123');
    expect(sessionId).toBeDefined();
    
    // Test security manager
    const securityManager = container.resolve('securityManager');
    const token = securityManager.generateToken({ user: 'test' });
    expect(token).toBeDefined();

    // Test theme manager
    const themeManager = container.resolve('themeManager');
    themeManager.setTheme('dark');
    expect(themeManager.getTheme()).toBe('dark');

    // Test AI manager
    const aiManager = container.resolve('aiManager');
    const prediction = aiManager.predict('test input');
    expect(prediction).toBeDefined();

    // Test event bus
    const eventBus = container.resolve('eventBus');
    const handler = jest.fn();
    eventBus.subscribe('testEvent', handler);
    eventBus.publish('testEvent', { data: 'test' });
    expect(handler).toHaveBeenCalledWith({ data: 'test' });
  });

  test('findById should throw when id is undefined or null', () => {
    const repository = container.resolve('repository');

    expect(() => {
      repository.findById(undefined);
    }).toThrow('Id is required');

    expect(() => {
      repository.findById(null);
    }).toThrow('Id is required');
  });

  test('findById should not throw for a valid id', () => {
    const repository = container.resolve('repository');

    expect(() => {
      repository.findById(1);
    }).not.toThrow();
  });

  test('findById should return undefined when entity is not found', () => {
    const repository = container.resolve('repository');

    const result = repository.findById(999);
    expect(result).toBeUndefined();
  });

  test('update should throw when entity is null or undefined', () => {
    const repository = container.resolve('repository');

    expect(() => {
      repository.update(1, null);
    }).toThrow('Entity must be a non-null object');

    expect(() => {
      repository.update(1, undefined);
    }).toThrow('Entity must be a non-null object');
  });

  test('update should throw when entity is an array', () => {
    const repository = container.resolve('repository');

    expect(() => {
      repository.update(1, ['a', 'b']);
    }).toThrow('Entity must be a non-null object');
  });

  test('update should throw when no rows are affected (entity not found)', () => {
    const repository = container.resolve('repository');
    const database = container.resolve('database');

    jest.spyOn(database, 'query').mockReturnValue({ rows: [], affectedRows: 0 });

    expect(() => {
      repository.update(999, { name: 'Ghost', description: 'Non-existent' });
    }).toThrow('Entity with id 999 not found for update');
  });

  test('update should return updated entity when rows are affected', () => {
    const repository = container.resolve('repository');
    const database = container.resolve('database');

    jest.spyOn(database, 'query').mockReturnValue({ rows: [], affectedRows: 1 });

    const result = repository.update(42, { name: 'Valid', description: 'Exists' });
    expect(result).toEqual({ id: 42, name: 'Valid', description: 'Exists' });
  });

  test('update should throw when id is undefined or null', () => {
    const repository = container.resolve('repository');

    expect(() => {
      repository.update(undefined, { name: 'test' });
    }).toThrow('Id is required');

    expect(() => {
      repository.update(null, { name: 'test' });
    }).toThrow('Id is required');
  });

  test('update should not call query when id is invalid', () => {
    const repository = container.resolve('repository');
    const database = container.resolve('database');

    const querySpy = jest.spyOn(database, 'query');

    expect(() => {
      repository.update(undefined, { name: 'test', description: 'test' });
    }).toThrow('Id is required');

    expect(querySpy).not.toHaveBeenCalled();
  });

  test('event bus should isolate failing handlers so other handlers still execute', () => {
    const eventBus = container.resolve('eventBus');

    const failingHandler = jest.fn(() => { throw new Error('Handler crashed'); });
    const workingHandler = jest.fn();

    eventBus.subscribe('testEvent', failingHandler);
    eventBus.subscribe('testEvent', workingHandler);

    expect(() => {
      eventBus.publish('testEvent', { data: 'test' });
    }).not.toThrow();

    expect(workingHandler).toHaveBeenCalledWith({ data: 'test' });
    expect(failingHandler).toHaveBeenCalledWith({ data: 'test' });
  });

  test('event bus should prevent duplicate handler subscriptions', () => {
    const eventBus = container.resolve('eventBus');

    const handler = jest.fn();

    eventBus.subscribe('testEvent', handler);
    eventBus.subscribe('testEvent', handler);

    eventBus.publish('testEvent', { data: 'test' });

    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledWith({ data: 'test' });
  });

  test('event bus should allow distinct handlers for the same event', () => {
    const eventBus = container.resolve('eventBus');

    const handlerA = jest.fn();
    const handlerB = jest.fn();

    eventBus.subscribe('testEvent', handlerA);
    eventBus.subscribe('testEvent', handlerB);

    eventBus.publish('testEvent', { data: 'test' });

    expect(handlerA).toHaveBeenCalledTimes(1);
    expect(handlerB).toHaveBeenCalledTimes(1);
  });

  test('event bus should not skip handlers when another handler unsubscribes during publish', () => {
    const eventBus = container.resolve('eventBus');

    const handlerA = jest.fn(() => {
      eventBus.unsubscribe('testEvent', handlerB);
    });
    const handlerB = jest.fn();
    const handlerC = jest.fn();

    eventBus.subscribe('testEvent', handlerA);
    eventBus.subscribe('testEvent', handlerB);
    eventBus.subscribe('testEvent', handlerC);

    eventBus.publish('testEvent', { data: 'first' });

    expect(handlerA).toHaveBeenCalledTimes(1);
    expect(handlerB).toHaveBeenCalledTimes(1);
    expect(handlerC).toHaveBeenCalledTimes(1);

    eventBus.publish('testEvent', { data: 'second' });

    expect(handlerA).toHaveBeenCalledTimes(2);
    expect(handlerB).toHaveBeenCalledTimes(1);
    expect(handlerC).toHaveBeenCalledTimes(2);
  });

  test('logger should pass full error object when transport fails', () => {
    const logger = container.resolve('logger');
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    const failingTransport = {
      write: jest.fn(() => { throw new Error('Transport crashed'); })
    };

    logger.addTransport(failingTransport);
    logger.info('test message');

    expect(consoleSpy).toHaveBeenCalled();
    const errorArg = consoleSpy.mock.calls[0][1];
    expect(errorArg).toBeInstanceOf(Error);
    expect(errorArg.message).toBe('Transport crashed');

    consoleSpy.mockRestore();
  });

  test('delete should throw when no rows are affected (entity not found)', () => {
    const repository = container.resolve('repository');
    const database = container.resolve('database');

    jest.spyOn(database, 'query').mockReturnValue({ rows: [], affectedRows: 0 });

    expect(() => {
      repository.delete(999);
    }).toThrow('Entity with id 999 not found for deletion');
  });

  test('delete should return true when rows are affected', () => {
    const repository = container.resolve('repository');
    const database = container.resolve('database');

    jest.spyOn(database, 'query').mockReturnValue({ rows: [], affectedRows: 1 });

    const result = repository.delete(42);
    expect(result).toBe(true);
  });

  test('delete should throw when id is undefined or null', () => {
    const repository = container.resolve('repository');

    expect(() => {
      repository.delete(undefined);
    }).toThrow('Id is required');

    expect(() => {
      repository.delete(null);
    }).toThrow('Id is required');
  });

  test('delete should not call query when id is invalid', () => {
    const repository = container.resolve('repository');
    const database = container.resolve('database');

    const querySpy = jest.spyOn(database, 'query');

    expect(() => {
      repository.delete(undefined);
    }).toThrow('Id is required');

    expect(querySpy).not.toHaveBeenCalled();
  });

  test('save should throw when entity is null or undefined', () => {
    const repository = container.resolve('repository');

    expect(() => {
      repository.save(null);
    }).toThrow('Entity must be a non-null object');

    expect(() => {
      repository.save(undefined);
    }).toThrow('Entity must be a non-null object');
  });

  test('save should throw when entity is an array', () => {
    const repository = container.resolve('repository');

    expect(() => {
      repository.save([1, 2, 3]);
    }).toThrow('Entity must be a non-null object');
  });

  test('save should throw when no rows are affected (insert failed)', () => {
    const repository = container.resolve('repository');
    const database = container.resolve('database');

    jest.spyOn(database, 'query').mockReturnValue({ rows: [], affectedRows: 0 });

    expect(() => {
      repository.save({ name: 'Ghost', description: 'Will not persist' });
    }).toThrow('Failed to insert entity');
  });

  test('save should return saved entity when rows are affected', () => {
    const repository = container.resolve('repository');
    const database = container.resolve('database');

    jest.spyOn(database, 'query').mockReturnValue({ rows: [], affectedRows: 1, insertId: 100 });

    const result = repository.save({ name: 'Valid', description: 'Persisted' });
    expect(result).toEqual({ id: 100, name: 'Valid', description: 'Persisted' });
  });

  test('should maintain singleton instances for singletons', () => {
    const config1 = container.resolve('configuration');
    const config2 = container.resolve('configuration');
    
    expect(config1).toBe(config2);
    
    const logger1 = container.resolve('logger');
    const logger2 = container.resolve('logger');
    
    expect(logger1).toBe(logger2);
  });
});

describe('Repository data-integrity — partial update returns full entity', () => {
  let db;
  let studentRepository;
  let academicRepository;

  function createAllTables() {
    db.query(`CREATE TABLE IF NOT EXISTS students (
      id INT PRIMARY KEY AUTO_INCREMENT,
      first_name VARCHAR(100) NOT NULL,
      last_name VARCHAR(100) NOT NULL,
      student_number VARCHAR(50) UNIQUE NOT NULL,
      email VARCHAR(255),
      date_of_birth VARCHAR(10),
      status VARCHAR(20) DEFAULT 'active',
      created_at VARCHAR(50),
      updated_at VARCHAR(50)
    )`);
    db.query(`CREATE TABLE IF NOT EXISTS academic_years (
      id INT PRIMARY KEY AUTO_INCREMENT,
      name VARCHAR(100) NOT NULL,
      start_date VARCHAR(10),
      end_date VARCHAR(10),
      status VARCHAR(20) DEFAULT 'active'
    )`);
    db.query(`CREATE TABLE IF NOT EXISTS terms (
      id INT PRIMARY KEY AUTO_INCREMENT,
      academic_year_id INT NOT NULL,
      name VARCHAR(100) NOT NULL,
      start_date VARCHAR(10),
      end_date VARCHAR(10),
      status VARCHAR(20) DEFAULT 'active'
    )`);
    db.query(`CREATE TABLE IF NOT EXISTS subjects (
      id INT PRIMARY KEY AUTO_INCREMENT,
      name VARCHAR(100) NOT NULL,
      code VARCHAR(50) UNIQUE NOT NULL,
      description TEXT,
      status VARCHAR(20) DEFAULT 'active'
    )`);
    db.query(`CREATE TABLE IF NOT EXISTS teachers (
      id INT PRIMARY KEY AUTO_INCREMENT,
      first_name VARCHAR(100) NOT NULL,
      last_name VARCHAR(100) NOT NULL,
      employee_number VARCHAR(50) UNIQUE NOT NULL,
      email VARCHAR(255),
      status VARCHAR(20) DEFAULT 'active'
    )`);
  }

  beforeEach(() => {
    db = new (require('../implementations/database'))();
    db.connect();
    createAllTables();
    studentRepository = new (require('../implementations/student-repository'))(db);
    academicRepository = new (require('../implementations/academic-structure-repository'))(db);
  });

  afterEach(() => {
    db.disconnect();
  });

  test('StudentRepository.update should return full entity after partial update', () => {
    const saved = studentRepository.save({
      first_name: 'John',
      last_name: 'Doe',
      student_number: 'S001',
      email: 'john@test.com',
      date_of_birth: '2000-01-01',
      status: 'active',
      created_at: '2024-01-01T00:00:00.000Z',
      updated_at: '2024-01-01T00:00:00.000Z'
    });

    const result = studentRepository.update(saved.id, { status: 'inactive' });

    expect(result.id).toBe(saved.id);
    expect(result.first_name).toBe('John');
    expect(result.last_name).toBe('Doe');
    expect(result.student_number).toBe('S001');
    expect(result.email).toBe('john@test.com');
    expect(result.status).toBe('inactive');
    expect(result.date_of_birth).toBe('2000-01-01');
  });

  test('StudentRepository.update with multiple partial fields returns full entity', () => {
    const saved = studentRepository.save({
      first_name: 'Jane',
      last_name: 'Smith',
      student_number: 'S002',
      email: 'jane@test.com',
      date_of_birth: '2001-05-15',
      status: 'active',
      created_at: '2024-01-01T00:00:00.000Z',
      updated_at: '2024-01-01T00:00:00.000Z'
    });

    const result = studentRepository.update(saved.id, {
      first_name: 'Janet',
      email: 'janet@test.com'
    });

    expect(result.id).toBe(saved.id);
    expect(result.first_name).toBe('Janet');
    expect(result.last_name).toBe('Smith');
    expect(result.student_number).toBe('S002');
    expect(result.email).toBe('janet@test.com');
    expect(result.status).toBe('active');
    expect(result.date_of_birth).toBe('2001-05-15');
  });

  test('AcademicStructureRepository.updateAcademicYear should return full entity', () => {
    const saved = academicRepository.saveAcademicYear({
      name: '2025-2026',
      start_date: '2025-01-01',
      end_date: '2025-12-31',
      status: 'active'
    });

    const result = academicRepository.updateAcademicYear(saved.id, { status: 'inactive' });

    expect(result.id).toBe(saved.id);
    expect(result.name).toBe('2025-2026');
    expect(result.start_date).toBe('2025-01-01');
    expect(result.end_date).toBe('2025-12-31');
    expect(result.status).toBe('inactive');
  });

  describe('StudentRepository.save persistence semantics', () => {
    test('should return persisted defaults when optional fields are omitted', () => {
      const result = studentRepository.save({
        first_name: 'Default',
        last_name: 'Test',
        student_number: 'S100',
        created_at: '2024-01-01T00:00:00.000Z',
        updated_at: '2024-01-01T00:00:00.000Z'
      });

      expect(result.id).toBeDefined();
      expect(result.first_name).toBe('Default');
      expect(result.last_name).toBe('Test');
      expect(result.student_number).toBe('S100');

      expect(result.email).toBeNull();
      expect(result.date_of_birth).toBeNull();
      expect(result.status).toBe('active');

      const stored = db.query('SELECT * FROM students WHERE id = ?', [result.id]).rows[0];
      expect(stored.email).toBeNull();
      expect(stored.date_of_birth).toBeNull();
      expect(stored.status).toBe('active');
    });

    test('should preserve explicit null email and date_of_birth', () => {
      const result = studentRepository.save({
        first_name: 'Null',
        last_name: 'Fields',
        student_number: 'S101',
        email: null,
        date_of_birth: null,
        status: 'active',
        created_at: '2024-01-01T00:00:00.000Z',
        updated_at: '2024-01-01T00:00:00.000Z'
      });

      expect(result.email).toBeNull();
      expect(result.date_of_birth).toBeNull();
      expect(result.status).toBe('active');

      const stored = db.query('SELECT * FROM students WHERE id = ?', [result.id]).rows[0];
      expect(stored.email).toBeNull();
      expect(stored.date_of_birth).toBeNull();
      expect(stored.status).toBe('active');
    });

    test('should return input values when all fields are provided', () => {
      const result = studentRepository.save({
        first_name: 'Full',
        last_name: 'Data',
        student_number: 'S102',
        email: 'full@test.com',
        date_of_birth: '2000-06-15',
        status: 'active',
        created_at: '2024-01-01T00:00:00.000Z',
        updated_at: '2024-01-01T00:00:00.000Z'
      });

      expect(result.email).toBe('full@test.com');
      expect(result.date_of_birth).toBe('2000-06-15');
      expect(result.status).toBe('active');

      const stored = db.query('SELECT * FROM students WHERE id = ?', [result.id]).rows[0];
      expect(stored.email).toBe('full@test.com');
      expect(stored.date_of_birth).toBe('2000-06-15');
      expect(stored.status).toBe('active');
    });
  });

  test('AcademicStructureRepository.updateSubject should return full entity', () => {
    const saved = academicRepository.saveSubject({
      name: 'Physics',
      code: 'PHY101',
      description: 'Introductory Physics',
      status: 'active'
    });

    const result = academicRepository.updateSubject(saved.id, { description: 'Advanced Physics' });

    expect(result.id).toBe(saved.id);
    expect(result.name).toBe('Physics');
    expect(result.code).toBe('PHY101');
    expect(result.description).toBe('Advanced Physics');
    expect(result.status).toBe('active');
  });

  test('AcademicStructureRepository.updateTeacher should return full entity', () => {
    const saved = academicRepository.saveTeacher({
      first_name: 'Alice',
      last_name: 'Wang',
      employee_number: 'TCH100',
      email: 'alice@school.edu',
      status: 'active'
    });

    const result = academicRepository.updateTeacher(saved.id, { email: 'alice.wang@school.edu' });

    expect(result.id).toBe(saved.id);
    expect(result.first_name).toBe('Alice');
    expect(result.last_name).toBe('Wang');
    expect(result.employee_number).toBe('TCH100');
    expect(result.email).toBe('alice.wang@school.edu');
    expect(result.status).toBe('active');
  });

  test('AcademicStructureRepository.updateTerm should return full entity', () => {
    const year = academicRepository.saveAcademicYear({
      name: '2026-2027',
      start_date: '2026-01-01',
      end_date: '2026-12-31',
      status: 'active'
    });

    const saved = academicRepository.saveTerm({
      academic_year_id: year.id,
      name: 'Spring Semester',
      start_date: '2026-01-15',
      end_date: '2026-05-15',
      status: 'active'
    });

    const result = academicRepository.updateTerm(saved.id, { name: 'Fall Semester' });

    expect(result.id).toBe(saved.id);
    expect(result.name).toBe('Fall Semester');
    expect(result.academic_year_id).toBe(year.id);
    expect(result.start_date).toBe('2026-01-15');
    expect(result.end_date).toBe('2026-05-15');
    expect(result.status).toBe('active');
  });

  describe('AcademicStructureRepository findAcademicYearById contract', () => {
    test('should throw when id is undefined', () => {
      expect(() => {
        academicRepository.findAcademicYearById(undefined);
      }).toThrow('Academic year id is required');
    });

    test('should throw when id is null', () => {
      expect(() => {
        academicRepository.findAcademicYearById(null);
      }).toThrow('Academic year id is required');
    });

    test('should return record when id exists', () => {
      const saved = academicRepository.saveAcademicYear({
        name: 'Contract-Test-Year',
        start_date: '2027-01-01',
        end_date: '2027-12-31',
        status: 'active'
      });
      const result = academicRepository.findAcademicYearById(saved.id);
      expect(result).toBeDefined();
      expect(result.id).toBe(saved.id);
      expect(result.name).toBe('Contract-Test-Year');
    });

    test('should return undefined when id does not exist', () => {
      const result = academicRepository.findAcademicYearById(99999);
      expect(result).toBeUndefined();
    });
  });

  describe('AcademicStructureRepository saveAcademicYear input validation', () => {
    test('should throw when data is null', () => {
      const querySpy = jest.spyOn(db, 'query');
      expect(() => {
        academicRepository.saveAcademicYear(null);
      }).toThrow('Academic year data must be a non-null object');
      expect(querySpy).not.toHaveBeenCalled();
      querySpy.mockRestore();
    });

    test('should throw when data is undefined', () => {
      const querySpy = jest.spyOn(db, 'query');
      expect(() => {
        academicRepository.saveAcademicYear(undefined);
      }).toThrow('Academic year data must be a non-null object');
      expect(querySpy).not.toHaveBeenCalled();
      querySpy.mockRestore();
    });

    test('should throw when data is an array', () => {
      const querySpy = jest.spyOn(db, 'query');
      expect(() => {
        academicRepository.saveAcademicYear(['name', '2025-01-01', '2025-12-31']);
      }).toThrow('Academic year data must be a non-null object');
      expect(querySpy).not.toHaveBeenCalled();
      querySpy.mockRestore();
    });

    test('should throw when data is a non-object primitive', () => {
      const querySpy = jest.spyOn(db, 'query');
      expect(() => {
        academicRepository.saveAcademicYear('invalid');
      }).toThrow('Academic year data must be a non-null object');
      expect(querySpy).not.toHaveBeenCalled();
      querySpy.mockRestore();
    });

    test('should save successfully with valid data', () => {
      const result = academicRepository.saveAcademicYear({
        name: 'Validation-Test-Year',
        start_date: '2028-01-01',
        end_date: '2028-12-31',
        status: 'active'
      });
      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
      expect(result.name).toBe('Validation-Test-Year');
      expect(result.status).toBe('active');
    });
  });
});
