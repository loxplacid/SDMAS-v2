const fs = require('fs');
const path = require('path');

class ConfigWatcher {
  constructor(configPath) {
    this.configPath = configPath;
    this.subscribers = new Set();
    this.watchers = new Map();
    this.isWatching = false;
    // Add thread safety with lock mechanism
    this._lock = false;
  }

  /**
   * Adds a subscriber to be notified of configuration changes
   * @param {Function} callback - Function to call when config changes
   * @throws {Error} If callback is not a function
   */
  subscribe(callback) {
    if (typeof callback !== 'function') {
      throw new Error('Subscriber must be a function');
    }
    this.subscribers.add(callback);
  }

  /**
   * Removes a subscriber
   * @param {Function} callback - Function to remove from subscribers
   */
  unsubscribe(callback) {
    this.subscribers.delete(callback);
  }

  /**
   * Starts watching the configuration file for changes
   * @throws {Error} If already watching or unable to start watch
   */
  start() {
    if (this.isWatching) return;
    
    try {
      // Add thread safety check
      if (this._lock) return;
      this._lock = true;
      
      // Watch the config file for changes
      const watcher = fs.watch(this.configPath, (eventType, filename) => {
        if (eventType === 'change') {
          this._notifySubscribers();
        }
      });
      
      this.watchers.set('config', watcher);
      this.isWatching = true;
    } catch (error) {
      console.error('Failed to start config watching:', error.message);
      throw error;
    } finally {
      this._lock = false;
    }
  }

  /**
   * Stops watching the configuration file
   */
  stop() {
    if (!this.isWatching) return;
    
    try {
      // Add thread safety check
      if (this._lock) return;
      this._lock = true;
      
      for (const [name, watcher] of this.watchers.entries()) {
        try {
          watcher.close();
        } catch (error) {
          console.error(`Failed to close watcher ${name}:`, error.message);
        }
      }
      
      this.watchers.clear();
      this.isWatching = false;
    } finally {
      this._lock = false;
    }
  }

  /**
   * Notifies all subscribers about configuration changes
   * @private
   */
  _notifySubscribers() {
    // Add thread safety for notification
    if (this._lock) return;
    
    try {
      this._lock = true;
      
      for (const subscriber of this.subscribers) {
        try {
          subscriber(this.configPath);
        } catch (error) {
          console.error('Error notifying subscriber:', error.message);
        }
      }
    } finally {
      this._lock = false;
    }
  }

  /**
   * Reloads configuration from file and notifies subscribers
   */
  reloadConfig() {
    if (!this.isWatching) return;
    
    this._notifySubscribers();
  }
}

module.exports = ConfigWatcher;
