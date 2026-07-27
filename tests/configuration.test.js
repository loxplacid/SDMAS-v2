const Configuration = require('../implementations/configuration');

describe('Configuration', () => {
  let config;

  beforeEach(() => {
    config = new Configuration();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('should set and get configuration values', () => {
    config.set('custom_key', 'custom_value');
    expect(config.get('custom_key')).toBe('custom_value');
  });

  test('should validate port configuration on set()', () => {
    expect(() => {
      config.set('port', 70000);
    }).toThrow(/Port must be a number between 1 and 65535/);

    config.set('port', 8080);
    expect(config.get('port')).toBe(8080);
  });

  test('should load valid configuration file successfully', () => {
    const mockData = JSON.stringify({
      port: 3000,
      database_url: 'postgres://localhost:5432/db',
      log_level: 'info',
      app_name: 'MyApp'
    });

    jest.spyOn(config.fs, 'accessSync').mockReturnValue(true);
    jest.spyOn(config.fs, 'readFileSync').mockReturnValue(mockData);

    config.loadFromFile('/path/to/config.json');

    expect(config.get('port')).toBe(3000);
    expect(config.get('database_url')).toBe('postgres://localhost:5432/db');
    expect(config.get('log_level')).toBe('info');
    expect(config.get('app_name')).toBe('MyApp');
  });

  test('should validate values when calling loadFromFile()', () => {
    const mockData = JSON.stringify({
      port: 99999,
      database_url: 'postgres://localhost:5432/db'
    });

    jest.spyOn(config.fs, 'accessSync').mockReturnValue(true);
    jest.spyOn(config.fs, 'readFileSync').mockReturnValue(mockData);

    expect(() => {
      config.loadFromFile('/path/to/invalid-config.json');
    }).toThrow(/Port must be a number between 1 and 65535/);
  });

  test('should preserve previous valid configuration if loadFromFile() validation fails', () => {
    config.set('existing_key', 'existing_value');

    const mockData = JSON.stringify({
      port: 8080,
      log_level: 'invalid_level'
    });

    jest.spyOn(config.fs, 'accessSync').mockReturnValue(true);
    jest.spyOn(config.fs, 'readFileSync').mockReturnValue(mockData);

    expect(() => {
      config.loadFromFile('/path/to/invalid-config.json');
    }).toThrow(/Log level must be one of: debug, info, warn, error/);

    expect(config.get('existing_key')).toBe('existing_value');
    expect(config.get('port')).toBeUndefined();
  });

  test('should validate multiple values before committing any changes', () => {
    const mockData = JSON.stringify({
      port: 8080,
      database_url: ''
    });

    jest.spyOn(config.fs, 'accessSync').mockReturnValue(true);
    jest.spyOn(config.fs, 'readFileSync').mockReturnValue(mockData);

    expect(() => {
      config.loadFromFile('/path/to/invalid-config.json');
    }).toThrow(/Database URL must be a non-empty string/);

    expect(config.get('port')).toBeUndefined();
  });

  test('should not corrupt configuration state when JSON is malformed', () => {
    config.set('initial_key', 'initial_value');

    jest.spyOn(config.fs, 'accessSync').mockReturnValue(true);
    jest.spyOn(config.fs, 'readFileSync').mockReturnValue('{ malformed json');

    expect(() => {
      config.loadFromFile('/path/to/malformed.json');
    }).toThrow(/Failed to load configuration/);

    expect(config.get('initial_key')).toBe('initial_value');
  });
});
