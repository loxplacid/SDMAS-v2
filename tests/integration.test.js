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
      'service',
      'sessionManager',
      'securityManager',
      'themeManager',
      'aiManager',
      'eventBus'
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
});
