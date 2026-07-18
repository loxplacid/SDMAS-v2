"""
Application bootstrap module.
Handles application lifecycle management and dependency injection setup.
"""

from typing import Dict, Any, Optional
import time
import logging
from dataclasses import dataclass

from .lifecycle import LifecycleManager
from .bootstrapper import Bootstrapper
from .startup import StartupManager
from .shutdown import ShutdownManager


@dataclass
class ApplicationConfig:
    """Application configuration data class."""
    name: str
    version: str
    debug: bool = False


class Application:
    """
    Main application class that manages the entire application lifecycle.
    
    This class owns the application lifecycle, dependency injection startup,
    configuration loading, logging initialization, plugin initialization,
    and service registration.
    """

    def __init__(self, config: ApplicationConfig):
        self.config = config
        self.lifecycle_manager = LifecycleManager()
        self.bootstrapper = Bootstrapper(self.lifecycle_manager)
        self.startup_manager = StartupManager()
        self.shutdown_manager = ShutdownManager()
        
        # Initialize timing tracking
        self._startup_start_time: Optional[float] = None
        self._startup_end_time: Optional[float] = None
        
    def initialize(self) -> bool:
        """
        Initialize the application by running all startup procedures.
        
        Returns:
            bool: True if initialization was successful, False otherwise.
        """
        try:
            self._startup_start_time = time.time()
            
            # Run bootstrapping process
            self.bootstrapper.bootstrap()
            
            # Execute startup sequence
            self.startup_manager.execute_startup_sequence()
            
            self._startup_end_time = time.time()
            
            return True
            
        except Exception as e:
            logging.error(f"Application initialization failed: {e}")
            return False
    
    def run(self) -> None:
        """
        Run the application in its main loop.
        
        This method should be called after successful initialization.
        """
        self.lifecycle_manager.set_state('running')
        
        # In a real implementation, this would contain the main event loop
        print(f"Application {self.config.name} is running...")
    
    def shutdown(self) -> None:
        """
        Gracefully shut down the application.
        
        This method ensures all resources are properly cleaned up.
        """
        try:
            self.lifecycle_manager.set_state('shutdown')
            
            # Execute shutdown sequence
            self.shutdown_manager.execute_shutdown_sequence()
            
            print("Application has been shut down successfully.")
            
        except Exception as e:
            logging.error(f"Error during application shutdown: {e}")
    
    def get_startup_time(self) -> Optional[float]:
        """
        Get the time taken for startup in seconds.
        
        Returns:
            float: Time taken for startup, or None if not yet started.
        """
        if self._startup_start_time is None:
            return None
            
        if self._startup_end_time is None:
            return time.time() - self._startup_start_time
            
        return self._startup_end_time - self._startup_start_time
