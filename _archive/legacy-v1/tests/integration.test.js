const path = require('path');
const fs = require('fs');
const setupDIContainer = require('../di-setup');

describe('Integration Tests', () => {
  let container;

  beforeEach(() => {
    container = setupDIContainer();
  });

  test('should be able to resolve all registered services without errors', () => {
    const serviceNames = [
      'configuration',
      'logger',
      'database',
      'repository',
      'migrationRunner',
      'service',
      'sessionManager',
      'securityManager',
      'themeManager',
      'aiManager',
      'eventBus',
      'studentRepository',
      'studentService',
      'academicStructureRepository',
      'academicStructureService'
    ];

    // All services should resolve without throwing errors
    expect(() => {
      serviceNames.forEach(name => container.resolve(name));
    }).not.toThrow();
  });

  test('should maintain proper dependency injection throughout the system', () => {
    const logger = container.resolve('logger');
    const database = container.resolve('database');
    const repository = container.resolve('repository');

    // Verify that repository has access to database
    expect(repository.database).toBe(database);
    
    // Verify that logger is properly instantiated
    expect(logger.constructor.name).toBe('Logger');
  });

  test('should support complex service interactions', () => {
    const logger = container.resolve('logger');
    const securityManager = container.resolve('securityManager');
    const sessionManager = container.resolve('sessionManager');

    // Test authentication flow
    const authResult = securityManager.authenticate('admin', 'password');
    expect(authResult).toBeDefined();
    
    if (authResult) {
      // Create a session for authenticated user
      const sessionId = sessionManager.createSession(authResult.userId);
      expect(sessionId).toBeDefined();
      
      // Validate the session
      const isValid = sessionManager.validateSession(sessionId);
      expect(isValid).toBe(true);
    }
  });

  test('should handle service lifecycle correctly', () => {
    // Test singleton behavior - same instance should be returned on multiple resolves
    const config1 = container.resolve('configuration');
    const config2 = container.resolve('configuration');
    
    expect(config1).toBe(config2);

    const logger1 = container.resolve('logger');
    const logger2 = container.resolve('logger');
    
    expect(logger1).toBe(logger2);
  });

  describe('migration startup integration', () => {
    test('should resolve migrationRunner from container', () => {
      const runner = container.resolve('migrationRunner');
      expect(runner.constructor.name).toBe('MigrationRunner');
    });

    test('migrationRunner should have access to database', () => {
      const runner = container.resolve('migrationRunner');
      const database = container.resolve('database');
      expect(runner.database).toBe(database);
    });

    test('startup should run pending migrations from migrations directory', () => {
      const { startup } = require('../di-setup');
      const appContainer = startup();
      const runner = appContainer.resolve('migrationRunner');
      const applied = runner.getAppliedMigrations();
      expect(applied.length).toBeGreaterThanOrEqual(1);
      expect(applied[0].version).toBe(1);
      expect(applied[0].name).toBe('initial-schema');
    });

    test('startup should be idempotent', () => {
      const { startup } = require('../di-setup');
      const appContainer1 = startup();
      const runner1 = appContainer1.resolve('migrationRunner');
      const firstApplied = runner1.getAppliedMigrations();
      expect(firstApplied.length).toBeGreaterThanOrEqual(1);
      expect(firstApplied[0].version).toBe(1);
      expect(firstApplied[0].name).toBe('initial-schema');

      const appContainer2 = startup();
      const runner2 = appContainer2.resolve('migrationRunner');
      const secondApplied = runner2.getAppliedMigrations();
      expect(secondApplied.length).toBeGreaterThanOrEqual(1);
      expect(secondApplied[0].version).toBe(1);
      expect(secondApplied[0].name).toBe('initial-schema');
    });
  });

  describe('student service DI integration', () => {
    test('should resolve studentRepository with database dependency', () => {
      const repo = container.resolve('studentRepository');
      const database = container.resolve('database');
      expect(repo.database).toBe(database);
    });

    test('should resolve studentService with studentRepository dependency', () => {
      const StudentRepository = require('../implementations/student-repository');
      const service = container.resolve('studentService');
      const database = container.resolve('database');
      expect(service.studentRepository).toBeInstanceOf(StudentRepository);
      expect(service.studentRepository.database).toBe(database);
    });
  });

  describe('academic structure DI integration', () => {
    test('should resolve academicStructureRepository with database dependency', () => {
      const repo = container.resolve('academicStructureRepository');
      const database = container.resolve('database');
      expect(repo.database).toBe(database);
    });

    test('should resolve academicStructureService with repository dependency', () => {
      const AcademicStructureRepository = require('../implementations/academic-structure-repository');
      const service = container.resolve('academicStructureService');
      const database = container.resolve('database');
      expect(service.repository).toBeInstanceOf(AcademicStructureRepository);
      expect(service.repository.database).toBe(database);
    });
  });
});
