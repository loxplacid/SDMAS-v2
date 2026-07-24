const { ILogger } = require('../interfaces');

class Logger extends ILogger {
  constructor() {
    super();
    this.level = 'info';
    this.formatters = new Map();
    this.transports = [];
  }

  /**
   * Adds a formatter for log messages
   * @param {string} type - The format type (e.g., 'json', 'simple')
   * @param {Function} formatter - Formatter function that processes the message
   */
  addFormatter(type, formatter) {
    if (typeof formatter !== 'function') {
      throw new Error('Formatter must be a function');
    }
    this.formatters.set(type, formatter);
  }

  /**
   * Adds a transport for log output
   * @param {Object} transport - Transport object with write method
   */
  addTransport(transport) {
    if (typeof transport.write !== 'function') {
      throw new Error('Transport must have a write method');
    }
    this.transports.push(transport);
  }

  /**
   * Formats and outputs a log message
   * @param {string} level - The log level
   * @param {string} message - The log message
   */
  _output(level, message) {
    const timestamp = new Date().toISOString();
    const formattedMessage = `[${level.toUpperCase()}] ${timestamp} - ${message}`;
    
    // Apply default formatter if available
    const defaultFormatter = this.formatters.get('default');
    const finalMessage = defaultFormatter ? 
      defaultFormatter(formattedMessage) : 
      formattedMessage;
      
    // Output to all transports
    for (const transport of this.transports) {
      try {
        transport.write(finalMessage);
      } catch (error) {
        console.error('Error in log transport:', error.message);
      }
    }
    
    // Also output to console by default
    if (this.transports.length === 0) {
      console.log(formattedMessage);
    }
  }

  /**
   * Logs a message at the specified level
   * @param {string} message - The log message
   */
  log(message) {
    this._output('log', message);
  }

  /**
   * Logs an info message
   * @param {string} message - The log message
   */
  info(message) {
    if (this._shouldLog('info')) {
      this._output('info', message);
    }
  }

  /**
   * Logs a warning message
   * @param {string} message - The log message
   */
  warn(message) {
    if (this._shouldLog('warn')) {
      this._output('warn', message);
    }
  }

  /**
   * Logs an error message
   * @param {string} message - The log message
   */
  error(message) {
    if (this._shouldLog('error')) {
      this._output('error', message);
    }
  }

  /**
   * Sets the minimum logging level
   * @param {string} level - The minimum level to log ('log', 'info', 'warn', 'error')
   */
  setLevel(level) {
    const validLevels = ['log', 'info', 'warn', 'error'];
    if (!validLevels.includes(level)) {
      throw new Error(`Invalid log level: ${level}. Must be one of ${validLevels.join(', ')}`);
    }
    this.level = level;
  }

  /**
   * Checks if a message at the given level should be logged
   * @param {string} level - The log level to check
   * @returns {boolean} True if the message should be logged
   */
  _shouldLog(level) {
    const levels = ['log', 'info', 'warn', 'error'];
    return levels.indexOf(level) >= levels.indexOf(this.level);
  }

  /**
   * Gets the current logging level
   * @returns {string} The current log level
   */
  getLevel() {
    return this.level;
  }
}

module.exports = Logger;
