const { IEventBus } = require('../interfaces');

class EventBus extends IEventBus {
  constructor() {
    super();
    this.subscribers = new Map();
  }

  subscribe(event, handler) {
    if (!this.subscribers.has(event)) {
      this.subscribers.set(event, []);
    }
    
    this.subscribers.get(event).push(handler);
  }

  publish(event, data) {
    const handlers = this.subscribers.get(event);
    if (handlers && handlers.length > 0) {
      handlers.forEach(handler => handler(data));
    }
  }

  unsubscribe(event, handler) {
    const handlers = this.subscribers.get(event);
    if (handlers) {
      const index = handlers.indexOf(handler);
      if (index !== -1) {
        handlers.splice(index, 1);
      }
    }
  }
}

module.exports = EventBus;
