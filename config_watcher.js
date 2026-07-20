const fs = require('fs');
const path = require('path');

class ConfigWatcher {
  constructor(configPath) {
    this.configPath = configPath;
    this.subscribers = new Set();
    this.watchers = new Map();
    this.isWatching = false;
  }

  /**
   * Adds a subscriber to be notified of configuration changes
   * @param {Function} callback - Function to call when config changes
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
   */
  start() {
    if (this.isWatching) return;
    
    try {
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
    }
  }

  /**
   * Stops watching the configuration file
   */
  stop() {
    if (!this.isWatching) return;
    
    for (const [name, watcher] of this.watchers.entries()) {
      try {
        watcher.close();
      } catch (error) {
        console.error(`Failed to close watcher ${name}:`, error.message);
      }
    }
    
    this.watchers.clear();
    this.isWatching = false;
  }

  /**
   * Notifies all subscribers about configuration changes
   * @private
   */
  _notifySubscribers() {
    for (const subscriber of this.subscribers) {
      try {
        subscriber(this.configPath);
      } catch (error) {
        console.error('Error notifying subscriber:', error.message);
      }
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
