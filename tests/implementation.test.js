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

  test('should maintain singleton instances for singletons', () => {
    const config1 = container.resolve('configuration');
    const config2 = container.resolve('configuration');
    
    expect(config1).toBe(config2);
    
    const logger1 = container.resolve('logger');
    const logger2 = container.resolve('logger');
    
    expect(logger1).toBe(logger2);
  });
});
