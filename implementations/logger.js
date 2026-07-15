const { ILogger } = require('../interfaces');

class Logger extends ILogger {
  constructor() {
    super();
    this.level = 'info';
  }

  log(message) {
    console.log(`[LOG] ${new Date().toISOString()} - ${message}`);
  }

  info(message) {
    console.info(`[INFO] ${new Date().toISOString()} - ${message}`);
  }

  warn(message) {
    console.warn(`[WARN] ${new Date().toISOString()} - ${message}`);
  }

  error(message) {
    console.error(`[ERROR] ${new Date().toISOString()} - ${message}`);
  }
}

module.exports = Logger;
