const DependencyInjectionContainer = require('../di-container');
const Configuration = require('../implementations/configuration');
const Logger = require('../implementations/logger');

describe('Dependency Injection Container', () => {
  let container;

  beforeEach(() => {
    container = new DependencyInjectionContainer();
  });

  afterEach(() => {
    container.clear();
  });

  test('should register and resolve services', () => {
    const mockService = jest.fn().mockReturnValue({ name: 'test' });
    
    container.register('testService', mockService);
    
    const service = container.resolve('testService');
    
    expect(service).toEqual({ name: 'test' });
    expect(mockService).toHaveBeenCalledTimes(1);
  });

  test('should resolve dependencies correctly', () => {
    const config = new Configuration();
    const logger = new Logger();
    
    // Register services with dependencies
    container.registerSingleton('configuration', () => config);
    container.registerSingleton('logger', () => logger);
    
    container.register('testService', (config, logger) => ({
      config,
      logger,
      name: 'dependencyTest'
    }), ['configuration', 'logger']);
    
    const service = container.resolve('testService');
    
    expect(service.name).toBe('dependencyTest');
    expect(service.config).toBe(config);
    expect(service.logger).toBe(logger);
  });

  test('should handle singleton services correctly', () => {
    let callCount = 0;
    
    container.registerSingleton('singletonService', () => {
      callCount++;
      return { id: `instance-${callCount}` };
    });
    
    const instance1 = container.resolve('singletonService');
    const instance2 = container.resolve('singletonService');
    
    expect(instance1).toBe(instance2);
    expect(callCount).toBe(1);
  });

  test('should throw error for unregistered service', () => {
    expect(() => {
      container.resolve('nonExistentService');
    }).toThrow("Service 'nonExistentService' not registered");
  });
});
