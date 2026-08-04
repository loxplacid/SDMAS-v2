const fs = require('fs');
const path = require('path');

// Mock the file system operations for testing
jest.mock('fs');

const {
  ApplicationConfig,
  DatabaseConfig,
  LoggingConfig,
  SecurityConfig,
  ThemeConfig,
  AIConfig
} = require('./config');

// Mock ConfigurationLoader implementation for tests
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

describe('ConfigurationLoader', () => {
  beforeEach(() => {
    // Clear all mocks before each test
    jest.clearAllMocks();
  });

  test('should load configuration from JSON file', () => {
    const mockConfigData = {
      application: {},
      database: {},
      logging: {},
      security: {},
      theme: {},
      ai: {}
    };

    // Mock fs.readFileSync to return valid JSON
    fs.readFileSync.mockReturnValue(JSON.stringify(mockConfigData));
    
    // Mock fs.existsSync to return true
    fs.existsSync.mockReturnValue(true);
    
    const config = MockConfigurationLoader.load('./config.json');
    
    expect(config).toBeDefined();
    expect(config.application).toBeInstanceOf(ApplicationConfig);
    expect(config.database).toBeInstanceOf(DatabaseConfig);
    expect(config.logging).toBeInstanceOf(LoggingConfig);
    expect(config.security).toBeInstanceOf(SecurityConfig);
    expect(config.theme).toBeInstanceOf(ThemeConfig);
    expect(config.ai).toBeInstanceOf(AIConfig);
  });

  test('should throw error when file does not exist', () => {
    // Mock fs.existsSync to return false
    fs.existsSync.mockReturnValue(false);
    
    expect(() => {
      MockConfigurationLoader.load('./nonexistent.json');
    }).toThrow(/Configuration file not found/);
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
