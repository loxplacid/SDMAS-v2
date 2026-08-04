class EnvironmentConfigurationProvider {
  static provide(config) {
    // Create a copy of the original config to avoid modifying it directly
    const result = {};
    
    // Copy all configuration objects
    Object.keys(config).forEach(key => {
      result[key] = Object.assign(Object.create(Object.getPrototypeOf(config[key])), config[key]);
    });
    
    // Override with environment variables
    if (process.env.APP_NAME) {
      result.application.name = process.env.APP_NAME;
    }
    
    if (process.env.DB_HOST) {
      result.database.host = process.env.DB_HOST;
    }
    
    if (process.env.DB_PORT) {
      const port = parseInt(process.env.DB_PORT, 10);
      if (!isNaN(port)) {
        result.database.port = port;
      } else {
        throw new Error('Invalid database port value in environment variable DB_PORT');
      }
    }
    
    if (process.env.LOG_LEVEL) {
      result.logging.level = process.env.LOG_LEVEL;
    }
    
    if (process.env.JWT_SECRET) {
      result.security.jwtSecret = process.env.JWT_SECRET;
    }
    
    if (process.env.THEME_NAME) {
      result.theme.name = process.env.THEME_NAME;
    }
    
    if (process.env.AI_MODEL_PATH) {
      result.ai.modelPath = process.env.AI_MODEL_PATH;
    }
    
    return result;
  }
}

module.exports = EnvironmentConfigurationProvider;
