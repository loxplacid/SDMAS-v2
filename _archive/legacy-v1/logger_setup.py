import logging
from typing import Optional
from pathlib import Path

# Import our modules
from logging_config import LoggingConfig, get_logger
from audit_logger import setup_audit_logging
from performance_logger import setup_performance_logging


class LoggerSetup:
    """Complete logger setup for production applications"""
    
    def __init__(self):
        self.logging_config = LoggingConfig()
        
    def setup_complete_logging(self,
                              app_name: str = "MyApp",
                              log_level: str = "INFO",
                              enable_console: bool = True,
                              enable_file: bool = True) -> logging.Logger:
        """
        Setup complete logging configuration for production
        
        Args:
            app_name: Name of the application
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            enable_console: Enable console logging
            enable_file: Enable file logging
            
        Returns:
            Configured logger instance with all features enabled
        """
        
        # Setup basic logging
        logger = self.logging_config.setup_logging(
            app_name=app_name,
            log_level=log_level,
            enable_console=enable_console,
            enable_file=enable_file
        )
        
        # Setup audit logging
        logger = setup_audit_logging(logger)
        
        # Setup performance logging
        logger = setup_performance_logging(logger)
        
        # Log startup message
        self._log_startup(logger, app_name)
        
        return logger
    
    def _log_startup(self, logger: logging.Logger, app_name: str):
        """Log application startup information"""
        logger.info(f"Application {app_name} started successfully")
        logger.info(f"Logging configured at level {logger.level}")


# Global instance
logger_setup = LoggerSetup()


def get_production_logger(app_name: str = "MyApp") -> logging.Logger:
    """
    Get a production-ready logger with all features enabled
    
    Args:
        app_name: Name of the application
        
    Returns:
        Configured logger instance ready for production use
    """
    return logger_setup.setup_complete_logging(app_name=app_name)
