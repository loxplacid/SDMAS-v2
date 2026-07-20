const { IConfiguration } = require('../interfaces');

class Configuration extends IConfiguration {
  constructor() {
    super();
    this._config = {};
    this._validators = new Map();
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
}

module.exports = Configuration;
