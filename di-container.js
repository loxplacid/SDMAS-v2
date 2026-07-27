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
    return this._resolveInternal(name, []);
  }

  /**
   * Internal recursive helper for resolving dependencies with chain tracking
   * @param {string} name - Service name to resolve
   * @param {Array<string>} chain - Current resolution chain
   * @returns {*} Resolved service instance
   * @private
   */
  _resolveInternal(name, chain) {
    if (chain.includes(name)) {
      throw new Error(`Circular dependency detected: ${chain.join(' -> ')} -> ${name}`);
    }

    if (this._singletons.has(name)) {
      return this._singletons.get(name);
    }

    const service = this._services.get(name);
    if (!service) {
      if (chain.length === 0) {
        throw new Error(`Service '${name}' not registered`);
      }
      throw new Error(`Service '${name}' not registered (required by ${chain.join(' -> ')})`);
    }

    const nextChain = [...chain, name];

    const resolvedDependencies = service.dependencies.map(depName =>
      this._resolveInternal(depName, nextChain)
    );

    const instance = service.factory(...resolvedDependencies);

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
