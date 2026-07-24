const { IConfiguration } = require('../interfaces');

class Configuration extends IConfiguration {
  constructor(configPath = null) {
    super();
    this._config = {};
    this._validators = new Map();
    this.configPath = configPath;
    this.watchers = new Set();
    // Use dependency injection for file system operations
    this.fs = require('fs');
    this.path = require('path');
    
    // Add validation for configuration values
    this.addValidator('database_url', (value) => {
      if (!value || typeof value !== 'string') {
        throw new Error('Database URL must be a non-empty string');
      }
    });
    
    this.addValidator('port', (value) => {
      if (typeof value !== 'number' || value < 1 || value > 65535) {
        throw new Error('Port must be a number between 1 and 65535');
      }
    });
    
    this.addValidator('log_level', (value) => {
      const validLevels = ['debug', 'info', 'warn', 'error'];
      if (!validLevels.includes(value)) {
        throw new Error(`Log level must be one of: ${validLevels.join(', ')}`);
      }
    });
  }

  /**
   * Adds a validator for a specific configuration key
   * @param {string} key - The configuration key to validate
   * @param {Function} validator - Validation function that throws on invalid input
   * @throws {Error} If validator is not a function
   */
  addValidator(key, validator) {
    if (typeof validator !== 'function') {
      throw new Error(`Validator for ${key} must be a function`);
    }
    this._validators.set(key, validator);
  }

  /**
   * Gets a configuration value by key
   * @param {string} key - The configuration key
   * @returns {*} The configuration value or undefined if not found
   */
  get(key) {
    return this._config[key];
  }

  /**
   * Sets a configuration value
   * @param {string} key - The configuration key
   * @param {*} value - The configuration value
   * @throws {Error} If validation fails
   */
  set(key, value) {
    // Validate the value before setting
    if (this._validators.has(key)) {
      const validator = this._validators.get(key);
      try {
        validator(value);
      } catch (error) {
        throw new Error(`Validation failed for configuration key "${key}": ${error.message}`);
      }
    }
    
    this._config[key] = value;
  }

  /**
   * Gets all configuration values
   * @returns {Object} A copy of the entire configuration object
   */
  getAll() {
    return { ...this._config };
  }

  /**
   * Loads configuration from file
   * @param {string} filePath - Path to the config file
   * @throws {Error} If loading fails or file is invalid
   */
  loadFromFile(filePath) {
    if (!filePath) {
      throw new Error('Configuration file path is required');
    }
    
    try {
      // Check if file exists and is readable
      this.fs.accessSync(filePath, this.fs.constants.R_OK);
      
      const configFile = this.fs.readFileSync(filePath, 'utf8');
      const parsedConfig = JSON.parse(configFile);
      
      // Clear current config and set new values
      this._config = {};
      for (const [key, value] of Object.entries(parsedConfig)) {
        this.set(key, value);
      }
      
      this.configPath = filePath;
    } catch (error) {
      throw new Error(`Failed to load configuration from ${filePath}: ${error.message}`);
    }
  }

  /**
   * Adds a config watcher to monitor file changes
   * @param {Object} watcher - ConfigWatcher instance
   * @throws {Error} If watcher is invalid
   */
  addWatcher(watcher) {
    if (!watcher || typeof watcher.subscribe !== 'function') {
      throw new Error('Invalid watcher provided');
    }
    
    // Subscribe to notifications from this watcher
    const notify = (filePath) => {
      try {
        this.loadFromFile(filePath);
      } catch (error) {
        console.error('Error reloading configuration:', error.message);
      }
    };
    
    watcher.subscribe(notify);
    this.watchers.add(watcher);
  }

  /**
   * Removes a config watcher
   * @param {Object} watcher - ConfigWatcher instance to remove
   */
  removeWatcher(watcher) {
    if (this.watchers.has(watcher)) {
      // Note: We don't unsubscribe here as the watcher might be used by others
      this.watchers.delete(watcher);
    }
  }

  /**
   * Gets all active watchers
   * @returns {Set} Set of active watchers
   */
  getWatchers() {
    return new Set(this.watchers);
  }

  /**
   * Saves current configuration to file
   * @param {string} filePath - Path to save the config file
   * @throws {Error} If saving fails
   */
  saveToFile(filePath) {
    if (!filePath) {
      throw new Error('File path is required for saving configuration');
    }

    try {
      const configString = JSON.stringify(this._config, null, 2);
      this.fs.writeFileSync(filePath, configString, 'utf8');
      this.configPath = filePath;
    } catch (error) {
      throw new Error(`Failed to save configuration to ${filePath}: ${error.message}`);
    }
  }

  /**
   * Gets a configuration value with default fallback
   * @param {string} key - The configuration key
   * @param {*} defaultValue - Default value if key not found
   * @returns {*} The configuration value or default if not found
   */
  getWithDefault(key, defaultValue) {
    return this._config[key] !== undefined ? this._config[key] : defaultValue;
  }

  /**
   * Checks if a configuration key exists
   * @param {string} key - The configuration key
   * @returns {boolean} True if the key exists, false otherwise
   */
  has(key) {
    return this._config.hasOwnProperty(key);
  }
  
  /**
   * Validates current configuration against all registered validators
   * @throws {Error} If any validation fails
   */
  validate() {
    for (const [key, value] of Object.entries(this._config)) {
      if (this._validators.has(key)) {
        const validator = this._validators.get(key);
        try {
          validator(value);
        } catch (error) {
          throw new Error(`Validation failed for ${key}: ${error.message}`);
        }
      }
    }
  }

  /**
   * Gets the current configuration path
   * @returns {string|null} The path to the config file or null if not set
   */
  getPath() {
    return this.configPath;
  }
}

module.exports = Configuration;
