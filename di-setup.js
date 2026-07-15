const DependencyInjectionContainer = require('./di-container');
const Configuration = require('./implementations/configuration');
const Logger = require('./implementations/logger');
const Database = require('./implementations/database');
const Repository = require('./implementations/repository');
const Service = require('./implementations/service');
const SessionManager = require('./implementations/session-manager');
const SecurityManager = require('./implementations/security-manager');
const ThemeManager = require('./implementations/theme-manager');
const AIManager = require('./implementations/ai-manager');
const EventBus = require('./implementations/event-bus');

function setupDIContainer() {
  const container = new DependencyInjectionContainer();

  // Register services
  container.registerSingleton('configuration', () => new Configuration());
  container.registerSingleton('logger', () => new Logger());
  
  // Database service (singleton)
  container.registerSingleton('database', (config, logger) => {
    const db = new Database();
    db.connect();
    return db;
  }, ['configuration', 'logger']);
  
  // Repository service
  container.register('repository', (database) => {
    return new Repository(database);
  }, ['database']);
  
  // Service
  container.registerSingleton('service', () => new Service());
  
  // Session Manager
  container.registerSingleton('sessionManager', () => new SessionManager());
  
  // Security Manager
  container.registerSingleton('securityManager', () => new SecurityManager());
  
  // Theme Manager
  container.registerSingleton('themeManager', () => new ThemeManager());
  
  // AI Manager
  container.registerSingleton('aiManager', () => new AIManager());
  
  // Event Bus
  container.registerSingleton('eventBus', () => new EventBus());

  return container;
}

module.exports = setupDIContainer;
