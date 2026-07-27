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
   * @returns {*} Resolved service instance
   */
  resolve(name) {
    // Create a new chain for each top-level resolution
    return this._resolveWithChain(name, []);
  }

  /**
   * Internal recursive resolver with chain tracking
   * @private
   * @param {string} name - Service name to resolve
   * @param {Array<string>} chain - Current resolution chain
   * @returns {*} Resolved service instance
   */
  _resolveWithChain(name, chain) {
    // Check for circular dependency
    if (chain.includes(name)) {
      const cyclePath = [...chain, name].join(' -> ');
      throw new Error(`Circular dependency detected: ${cyclePath}`);
    }

    // Check if already resolved as singleton
    if (this._singletons.has(name)) {
      return this._singletons.get(name);
    }

    // Look up service
    const service = this._services.get(name);
    if (!service) {
      // If we're at the top level, throw original error format
      if (chain.length === 0) {
        throw new Error(`Service '${name}' not registered`);
      }
      
      // Otherwise provide context about who required it
      const chainPath = chain.join(' -> ');
      throw new Error(`Service '${name}' not registered (required by ${chainPath})`);
    }

    // Build the next chain with current service added
    const nextChain = [...chain, name];

    // Resolve dependencies first
    const resolvedDependencies = service.dependencies.map(depName => 
      this._resolveWithChain(depName, nextChain)
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
