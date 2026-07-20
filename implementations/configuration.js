const { IConfiguration } = require('../interfaces');
const fs = require('fs');

class Configuration extends IConfiguration {
  constructor(configPath = null) {
    super();
    this._config = {};
    this._validators = new Map();
    this.configPath = configPath;
    this.watchers = new Set();
  }

  // Add validator for a specific key
  addValidator(key, validator) {
    if (typeof validator !== 'function') {
      throw new Error(`Validator for ${key} must be a function`);
    }
    this._validators.set(key, validator);
  }

  get(key) {
    return this._config[key];
  }

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

  getAll() {
    return { ...this._config };
  }

  /**
   * Loads configuration from file
   * @param {string} filePath - Path to the config file
   */
  loadFromFile(filePath) {
    if (!filePath) {
      throw new Error('Configuration file path is required');
    }
    
    try {
      const configFile = fs.readFileSync(filePath, 'utf8');
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
}

module.exports = Configuration;
