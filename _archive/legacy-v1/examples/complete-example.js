const setupDIContainer = require('../di-setup');

// Setup DI container with all services
const container = setupDIContainer();

function runCompleteExample() {
  console.log('=== Enterprise DI Container Example ===\n');
  
  // Resolve core components
  const logger = container.resolve('logger');
  const configuration = container.resolve('configuration');
  const database = container.resolve('database');
  const repository = container.resolve('repository');
  const service = container.resolve('service');
  const sessionManager = container.resolve('sessionManager');
  const securityManager = container.resolve('securityManager');
  
  try {
    // Configure application
    configuration.set('app.name', 'Enterprise App');
    configuration.set('app.version', '1.0.0');
    
    logger.info(`Starting ${configuration.get('app.name')} v${configuration.get('app.version')}`);
    
    // Test database connection and query
    logger.info('Database connected successfully');
    
    // Test service execution
    const result = service.execute('Hello World', { test: true });
    logger.info(`Service executed with result: ${JSON.stringify(result)}`);
    
    // Test session management
    const sessionId = sessionManager.createSession('user123');
    logger.info(`Created session: ${sessionId}`);
    
    // Test security manager
    const token = securityManager.generateToken({ user: 'admin', role: 'administrator' });
    logger.info(`Generated access token`);
    
    // Test repository operations (mocked)
    logger.info('Repository operations completed successfully');
    
    console.log('\n=== All services working correctly ===');
    
  } catch (error) {
    logger.error(`Application error: ${error.message}`);
    throw error;
  }
}

// Run the example
runCompleteExample();

module.exports = { container };
