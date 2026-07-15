const { IConfiguration } = require('../interfaces');

class Configuration extends IConfiguration {
  constructor() {
    super();
    this._config = {};
  }

  get(key) {
    return this._config[key];
  }

  set(key, value) {
    this._config[key] = value;
  }

  getAll() {
    return { ...this._config };
  }
}

module.exports = Configuration;
