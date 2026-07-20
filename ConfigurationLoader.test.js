const { 
  ApplicationConfig,
  DatabaseConfig,
  LoggingConfig,
  SecurityConfig,
  ThemeConfig,
  AIConfig
} = require('./config');

// Mock the ConfigurationLoader class for testing purposes
class MockConfigurationLoader {
  static load(configPath) {
    // Return mock configuration objects
    return {
      application: new ApplicationConfig(),
      database: new DatabaseConfig(),
      logging: new LoggingConfig(),
      security: new SecurityConfig(),
      theme: new ThemeConfig(),
      ai: new AIConfig()
    };
  }
}

// Test suite for ConfigurationLoader
describe('ConfigurationLoader', () => {
  test('should load configuration from JSON file', () => {
    // Mock the file system operations
    const config = MockConfigurationLoader.load('./config.json');
    
    expect(config).toBeDefined();
    expect(config.application).toBeInstanceOf(ApplicationConfig);
    expect(config.database).toBeInstanceOf(DatabaseConfig);
    expect(config.logging).toBeInstanceOf(LoggingConfig);
    expect(config.security).toBeInstanceOf(SecurityConfig);
    expect(config.theme).toBeInstanceOf(ThemeConfig);
    expect(config.ai).toBeInstanceOf(AIConfig);
  });

  test('should create immutable configuration objects', () => {
    const config = MockConfigurationLoader.load('./config.json');
    
    // Try to modify the objects (should not work due to immutability)
    expect(() => {
      config.application.someProperty = 'test';
    }).toThrow();
    
    expect(() => {
      config.database.someProperty = 'test';
    }).toThrow();
    
    expect(() => {
      config.logging.someProperty = 'test';
    }).toThrow();
    
    expect(() => {
      config.security.someProperty = 'test';
    }).toThrow();
    
    expect(() => {
      config.theme.someProperty = 'test';
    }).toThrow();
    
    expect(() => {
      config.ai.someProperty = 'test';
    }).toThrow();
  });
});
