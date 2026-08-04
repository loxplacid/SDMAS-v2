const setupDIContainer = require('../di-setup');

// Setup the DI container with all services
const container = setupDIContainer();

// Example of how to use the container in an application
function main() {
  // Resolve required components
  const logger = container.resolve('logger');
  const database = container.resolve('database');
  const repository = container.resolve('repository');
  const service = container.resolve('service');
  
  try {
    // Use services without manual instantiation
    logger.info('Application started');
    
    // Perform operations using DI-resolved components
    const result = service.execute('Hello World', { test: true });
    logger.info(`Service execution result: ${JSON.stringify(result)}`);
    
    // Database operations
    database.query('SELECT * FROM users WHERE id = ?', [1]);
    
    // Repository operations
    repository.findAll();
    
  } catch (error) {
    logger.error(`Application error: ${error.message}`);
  }
}

main();

module.exports = { container };
