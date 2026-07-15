import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import json
import logging
from logging.handlers import RotatingFileHandler
import coloredlogs
from datetime import datetime


class LoggingConfig:
    """Production-grade logging configuration manager"""
    
    def __init__(self, config_dir: str = "./config"):
        self.config_dir = Path(config_dir)
        self.log_dir = self.config_dir / "logs"
        self.log_dir.mkdir(exist_ok=True)
        
    def setup_logging(self, 
                     app_name: str = "MyApp",
                     log_level: str = "INFO",
                     enable_console: bool = True,
                     enable_file: bool = True,
                     max_log_size: int = 10 * 1024 * 1024,  # 10MB
                     backup_count: int = 5) -> logging.Logger:
        """
        Setup comprehensive logging configuration
        
        Args:
            app_name: Name of the application
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            enable_console: Enable console logging
            enable_file: Enable file logging
            max_log_size: Maximum size for log files before rotation
            backup_count: Number of backup log files to keep
            
        Returns:
            Configured logger instance
        """
        
        # Create logger
        logger = logging.getLogger(app_name)
        logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Setup console handler with colors if enabled
        if enable_console:
            self._setup_console_handler(logger, app_name)
            
        # Setup file handler for regular logs
        if enable_file:
            self._setup_file_handler(logger, app_name, max_log_size, backup_count)
            
        # Setup audit log handler
        self._setup_audit_handler(logger, app_name, max_log_size, backup_count)
        
        return logger
    
    def _setup_console_handler(self, logger: logging.Logger, app_name: str):
        """Setup colored console logging"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            f'%(asctime)s - {app_name} - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Use coloredlogs for pretty console output
        if not logger.handlers:
            coloredlogs.install(level=logging.INFO, 
                              fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    def _setup_file_handler(self, logger: logging.Logger, app_name: str, 
                           max_log_size: int, backup_count: int):
        """Setup rotating file handler for regular logs"""
        log_file = self.log_dir / f"{app_name}.log"
        
        # Create rotating file handler
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_log_size,
            backupCount=backup_count
        )
        
        # Set formatter for file logs
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    def _setup_audit_handler(self, logger: logging.Logger, app_name: str,
                            max_log_size: int, backup_count: int):
        """Setup audit log handler for security-sensitive logs"""
        audit_file = self.log_dir / f"{app_name}_audit.log"
        
        # Create rotating file handler for audit logs
        audit_handler = RotatingFileHandler(
            audit_file,
            maxBytes=max_log_size,
            backupCount=backup_count
        )
        
        # Set formatter for audit logs (structured JSON)
        audit_formatter = logging.Formatter('%(message)s')
        audit_handler.setFormatter(audit_formatter)
        logger.addHandler(audit_handler)


# Global instance for easy access
logging_config = LoggingConfig()


def get_logger(app_name: str = "MyApp") -> logging.Logger:
    """Get configured logger instance"""
    return logging_config.setup_logging(app_name=app_name)
