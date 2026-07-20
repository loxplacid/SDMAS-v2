const fs = require('fs');
const path = require('path');

class ConfigurationLoader {
  static load(configPath) {
    // Validate file existence
    if (!this.fileExists(configPath)) {
      throw new Error(`Configuration file not found: ${configPath}`);
    }
    
    // Read and parse JSON
    const configData = this.readFile(configPath);
    const parsedConfig = JSON.parse(configData);
    
    // Validate and create configuration models
    return this.deserialize(parsedConfig);
  }

  static fileExists(filePath) {
    try {
      return fs.existsSync(filePath);
    } catch (error) {
      throw new Error(`Error checking file existence: ${error.message}`);
    }
  }

  static readFile(filePath) {
    try {
      const data = fs.readFileSync(filePath, 'utf8');
      return data;
    } catch (error) {
      throw new Error(`Error reading configuration file: ${error.message}`);
    }
  }

  static deserialize(configData) {
    const config = {};
    
    if (configData.application) {
      config.application = new ApplicationConfig();
      Object.assign(config.application, configData.application);
    }
    
    if (configData.database) {
      config.database = new DatabaseConfig();
      Object.assign(config.database, configData.database);
    }
    
    if (configData.logging) {
      config.logging = new LoggingConfig();
      Object.assign(config.logging, configData.logging);
    }
    
    if (configData.security) {
      config.security = new SecurityConfig();
      Object.assign(config.security, configData.security);
    }
    
    if (configData.theme) {
      config.theme = new ThemeConfig();
      Object.assign(config.theme, configData.theme);
    }
    
    if (configData.ai) {
      config.ai = new AIConfig();
      Object.assign(config.ai, configData.ai);
    }
    
    return config;
  }
}

module.exports = ConfigurationLoader;
