const { IConfiguration } = require('./interfaces');

class SecretsProvider {
  constructor(config) {
    if (!config || !(config instanceof IConfiguration)) {
      throw new Error('Configuration is required for SecretsProvider');
    }
    
    this.config = config;
    this.secretsCache = new Map();
  }

  /**
   * Retrieves a secret value by key
   * @param {string} key - The secret key to retrieve
   * @returns {string} The secret value
   * @throws {Error} If the secret is not found or invalid
   */
  getSecret(key) {
    if (!key || typeof key !== 'string') {
      throw new Error('Secret key must be a non-empty string');
    }

    // Check cache first
    if (this.secretsCache.has(key)) {
      return this.secretsCache.get(key);
    }

    try {
      const secret = this.config.get(`secret:${key}`);
      
      if (secret === undefined || secret === null) {
        throw new Error(`Secret "${key}" not found in configuration`);
      }
      
      // Validate that the secret is a string
      if (typeof secret !== 'string') {
        throw new Error(`Secret "${key}" must be a string value`);
      }

      // Cache the secret for future requests
      this.secretsCache.set(key, secret);
      
      return secret;
    } catch (error) {
      throw new Error(`Failed to retrieve secret "${key}": ${error.message}`);
    }
  }

  /**
   * Retrieves an API key by name
   * @param {string} apiKeyName - The name of the API key to retrieve
   * @returns {string} The API key value
   * @throws {Error} If the API key is not found or invalid
   */
  getApiKey(apiKeyName) {
    if (!apiKeyName || typeof apiKeyName !== 'string') {
      throw new Error('API key name must be a non-empty string');
    }

    try {
      const secret = this.config.get(`api_key:${apiKeyName}`);
      
      if (secret === undefined || secret === null) {
        throw new Error(`API key "${apiKeyName}" not found in configuration`);
      }
      
      // Validate that the API key is a string
      if (typeof secret !== 'string') {
        throw new Error(`API key "${apiKeyName}" must be a string value`);
      }

      return secret;
    } catch (error) {
      throw new Error(`Failed to retrieve API key "${apiKeyName}": ${error.message}`);
    }
  }

  /**
   * Retrieves a database password
   * @param {string} dbConnectionName - The name of the database connection
   * @returns {string} The database password
   * @throws {Error} If the database password is not found or invalid
   */
  getDatabasePassword(dbConnectionName) {
    if (!dbConnectionName || typeof dbConnectionName !== 'string') {
      throw new Error('Database connection name must be a non-empty string');
    }

    try {
      const secret = this.config.get(`database_password:${dbConnectionName}`);
      
      if (secret === undefined || secret === null) {
        throw new Error(`Database password for "${dbConnectionName}" not found in configuration`);
      }
      
      // Validate that the database password is a string
      if (typeof secret !== 'string') {
        throw new Error(`Database password for "${dbConnectionName}" must be a string value`);
      }

      return secret;
    } catch (error) {
      throw new Error(`Failed to retrieve database password for "${dbConnectionName}": ${error.message}`);
    }
  }

  /**
   * Sets a secret value
   * @param {string} key - The secret key
   * @param {string} value - The secret value
   */
  setSecret(key, value) {
    if (!key || typeof key !== 'string') {
      throw new Error('Secret key must be a non-empty string');
    }
    
    if (typeof value !== 'string') {
      throw new Error('Secret value must be a string');
    }

    this.config.set(`secret:${key}`, value);
    this.secretsCache.delete(key); // Remove from cache when updated
  }

  /**
   * Clears the secrets cache
   */
  clearCache() {
    this.secretsCache.clear();
  }
}

module.exports = SecretsProvider;
