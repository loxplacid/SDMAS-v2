class DependencyInjectionContainer {
  constructor() {
    this._services = new Map();
    this._singletons = new Map();
  }

  /**
   * Register a service with its dependencies
   * @param {string} name - Service name
   * @param {Function} factory - Factory function to create the instance
   * @param {Array<string>} dependencies - Array of dependency names
   */
  register(name, factory, dependencies = []) {
    this._services.set(name, { factory, dependencies });
  }

  /**
   * Resolve a service by name with all its dependencies injected
   * @param {string} name - Service name to resolve
   * @param {Array<string>} chain - Current resolution chain
   * @returns {*} Resolved service instance
   */
  resolve(name, chain = []) {
    // Check for circular dependency
    if (chain.includes(name)) {
      throw new Error(`Circular dependency detected: ${chain.join(' -> ')} -> ${name}`);
    }

    // Check if already resolved as singleton
    if (this._singletons.has(name)) {
      return this._singletons.get(name);
    }

    // Look up service
    const service = this._services.get(name);
    if (!service) {
      if (chain.length === 0) {
        throw new Error(`Service '${name}' not registered`);
      }
      throw new Error(`Service '${name}' not registered (required by ${chain.join(' -> ')})`);
    }

    // Build the next resolution chain
    const nextChain = [...chain, name];

    // Resolve dependencies first
    const resolvedDependencies = service.dependencies.map(depName => 
      this.resolve(depName, nextChain)
    );

    // Create instance with dependencies injected
    const instance = service.factory(...resolvedDependencies);

    // Cache singleton instances
    if (service.singleton) {
      this._singletons.set(name, instance);
    }

    return instance;
  }

  /**
   * Register a singleton service
   * @param {string} name - Service name
   * @param {Function} factory - Factory function to create the instance
   * @param {Array<string>} dependencies - Array of dependency names
   */
  registerSingleton(name, factory, dependencies = []) {
    this._services.set(name, { 
      factory, 
      dependencies,
      singleton: true 
    });
  }

  /**
   * Clear all registered services and singletons
   */
  clear() {
    this._services.clear();
    this._singletons.clear();
  }
}

module.exports = DependencyInjectionContainer;
