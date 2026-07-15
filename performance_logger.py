import time
import logging
from typing import Any, Dict, Optional, Callable
from functools import wraps
from datetime import datetime


class PerformanceLogger:
    """Performance monitoring and logging"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def log_performance(self, 
                      operation_name: str,
                      start_time: float,
                      end_time: float,
                      additional_info: Optional[Dict[str, Any]] = None):
        """
        Log performance metrics for an operation
        
        Args:
            operation_name: Name of the operation being measured
            start_time: Start time in seconds since epoch
            end_time: End time in seconds since epoch
            additional_info: Additional context about the operation
        """
        
        duration = end_time - start_time
        performance_data = {
            'operation': operation_name,
            'duration_ms': round(duration * 1000, 2),
            'start_time': datetime.fromtimestamp(start_time).isoformat(),
            'end_time': datetime.fromtimestamp(end_time).isoformat(),
            'additional_info': additional_info or {}
        }
        
        self.logger.info(f"PERFORMANCE: {operation_name} took {duration:.4f}s", 
                        extra={'performance_data': performance_data})
    
    def log_function_performance(self, operation_name: Optional[str] = None):
        """
        Decorator to automatically measure and log function execution time
        
        Args:
            operation_name: Name of the operation (defaults to function name)
        """
        
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    end_time = time.time()
                    name = operation_name or func.__name__
                    self.log_performance(name, start_time, end_time)
            
            return wrapper
        
        return decorator


# Global performance logger instance
performance_logger = None


def setup_performance_logging(logger: logging.Logger):
    """Setup performance logging for the application"""
    global performance_logger
    performance_logger = PerformanceLogger(logger)
    
    # Add a method to the logger for easy access
    def log_performance(operation_name, start_time, end_time, additional_info=None):
        if performance_logger:
            performance_logger.log_performance(
                operation_name=operation_name,
                start_time=start_time,
                end_time=end_time,
                additional_info=additional_info
            )
    
    logger.performance = log_performance
    
    # Add decorator method to the logger
    def log_function_performance(operation_name=None):
        if performance_logger:
            return performance_logger.log_function_performance(operation_name)
        return lambda f: f
    
    logger.log_function_performance = log_function_performance
    
    return logger


def get_performance_logger() -> PerformanceLogger:
    """Get the performance logger instance"""
    if performance_logger is None:
        raise RuntimeError("Performance logging not initialized. Call setup_performance_logging first.")
    return performance_logger
