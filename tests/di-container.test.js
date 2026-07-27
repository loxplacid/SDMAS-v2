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

  // New tests for circular dependency detection
  test('should detect direct cycle: a -> b -> a', () => {
    container.register('a', (b) => ({ b }), ['b']);
    container.register('b', (a) => ({ a }), ['a']);
    
    expect(() => {
      container.resolve('a');
    }).toThrow(/Circular dependency detected.*a -> b -> a/);
  });

  test('should detect self cycle: a -> a', () => {
    container.register('a', (a) => ({ a }), ['a']);
    
    expect(() => {
      container.resolve('a');
    }).toThrow(/Circular dependency detected.*a -> a/);
  });

  test('should detect indirect cycle: a -> b -> c -> a', () => {
    container.register('a', (b) => ({ b }), ['b']);
    container.register('b', (c) => ({ c }), ['c']);
    container.register('c', (a) => ({ a }), ['a']);
    
    expect(() => {
      container.resolve('a');
    }).toThrow(/Circular dependency detected.*a -> b -> c -> a/);
  });

  test('should provide context for missing dependencies', () => {
    container.register('a', (x) => x, ['x']);
    
    expect(() => {
      container.resolve('a');
    }).toThrow(/Service 'x' not registered \(required by a\)/);
  });

  test('should preserve existing behavior for direct missing service error', () => {
    expect(() => {
      container.resolve('nonExistentService');
    }).toThrow("Service 'nonExistentService' not registered");
  });

  test('should resolve diamond dependency graph correctly', () => {
    // a depends on b and c; both b and c depend on d
    let dInstanceCount = 0;
    
    container.registerSingleton('d', () => {
      dInstanceCount++;
      return { id: 'd' };
    });
    
    container.register('b', (d) => ({ d }), ['d']);
    container.register('c', (d) => ({ d }), ['d']);
    container.register('a', (b, c) => ({ b, c }), ['b', 'c']);
    
    const result = container.resolve('a');
    
    expect(result.b.d).toEqual({ id: 'd' });
    expect(result.c.d).toEqual({ id: 'd' });
    expect(dInstanceCount).toBe(1); // Should be singleton
  });
});
