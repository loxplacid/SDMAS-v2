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

  test('should detect a direct circular dependency (a -> b -> a)', () => {
    container.register('a', (b) => ({ b }), ['b']);
    container.register('b', (a) => ({ a }), ['a']);

    expect(() => {
      container.resolve('a');
    }).toThrow(/Circular dependency detected: a -> b -> a/);
  });

  test('should detect a self-referential circular dependency', () => {
    container.register('a', (a) => ({ a }), ['a']);

    expect(() => {
      container.resolve('a');
    }).toThrow(/Circular dependency detected: a -> a/);
  });

  test('should detect an indirect circular dependency (a -> b -> c -> a)', () => {
    container.register('a', (b) => ({ b }), ['b']);
    container.register('b', (c) => ({ c }), ['c']);
    container.register('c', (a) => ({ a }), ['a']);

    expect(() => {
      container.resolve('a');
    }).toThrow(/Circular dependency detected: a -> b -> c -> a/);
  });

  test('should include the requesting chain when a nested dependency is missing', () => {
    container.register('a', (x) => x, ['x']);

    expect(() => {
      container.resolve('a');
    }).toThrow("Service 'x' not registered (required by a)");
  });

  test('should disconnect singletons on clear', () => {
    const disconnect = jest.fn();
    container.registerSingleton('disposable', () => ({ disconnect }));

    container.resolve('disposable');
    container.clear();

    expect(disconnect).toHaveBeenCalledTimes(1);
  });

  test('should resolve a diamond dependency graph without a false-positive cycle', () => {
    let dCallCount = 0;

    container.registerSingleton('d', () => {
      dCallCount++;
      return { id: 'd-instance' };
    });

    container.register('b', (d) => ({ d }), ['d']);
    container.register('c', (d) => ({ d }), ['d']);
    container.register('a', (b, c) => ({ b, c }), ['b', 'c']);

    const result = container.resolve('a');

    expect(result.b.d).toBe(result.c.d);
    expect(dCallCount).toBe(1);
  });
});
