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
    
    The Application class composes all core bootstrap components:
    - LifecycleManager: Manages application states
    - Bootstrapper: Coordinates startup activities
    - StartupManager: Defines startup pipeline stages
    - ShutdownManager: Handles graceful termination
    
    All components are wired together to provide a cohesive application lifecycle
    management system.
    """

    def __init__(self, config: ApplicationConfig):
        """
        Initialize the application with configuration.
        
        Args:
            config (ApplicationConfig): Application configuration settings
        """
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
        
        This method orchestrates the complete initialization process using
        the composed components. It runs bootstrapping activities followed
        by the full startup sequence.
        
        Returns:
            bool: True if initialization was successful, False otherwise.
        """
        try:
            self._startup_start_time = time.time()
            
            # Run bootstrapping process - this coordinates all startup activities
            self.bootstrapper.bootstrap()
            
            # Execute startup sequence - this runs the defined pipeline stages
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
        It sets the lifecycle to running state and would contain
        the main event loop in a real implementation.
        """
        self.lifecycle_manager.set_state('running')
        
        # In a real implementation, this would contain the main event loop
        print(f"Application {self.config.name} is running...")
    
    def shutdown(self) -> None:
        """
        Gracefully shut down the application.
        
        This method ensures all resources are properly cleaned up using
        the composed shutdown manager which handles proper cleanup order.
        """
        try:
            # Set lifecycle to stopping state
            self.lifecycle_manager.set_state('stopping')
            
            # Execute shutdown sequence - this cleans up components in reverse order
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


# Test cases
if __name__ == "__main__":
    # Configure logging for testing
    logging.basicConfig(level=logging.INFO)
    
    # Create application with minimal config
    config = ApplicationConfig(name="TestApp", version="1.0.0")
    app = Application(config)
    
    # Verify all components are properly composed
    assert hasattr(app, 'lifecycle_manager')
    assert hasattr(app, 'bootstrapper')
    assert hasattr(app, 'startup_manager')
    assert hasattr(app, 'shutdown_manager')
    
    print("✓ All bootstrap components are properly composed")
    
    # Test that methods exist and are callable
    assert hasattr(app, 'initialize')
    assert hasattr(app, 'run')
    assert hasattr(app, 'shutdown')
    assert hasattr(app, 'get_startup_time')
    
    print("✓ All application methods are defined")
    
    # Verify component types
    assert isinstance(app.lifecycle_manager, LifecycleManager)
    assert isinstance(app.bootstrapper, Bootstrapper)
    assert isinstance(app.startup_manager, StartupManager)
    assert isinstance(app.shutdown_manager, ShutdownManager)
    
    print("✓ All components are of correct types")
    
    # Test that initialization method exists and is callable
    assert callable(app.initialize)
    print("✓ initialize() method is callable")
    
    # Test that run method exists and is callable
    assert callable(app.run)
    print("✓ run() method is callable")
    
    # Test that shutdown method exists and is callable
    assert callable(app.shutdown)
    print("✓ shutdown() method is callable")
    
    # Test that get_startup_time method exists and is callable
    assert callable(app.get_startup_time)
    print("✓ get_startup_time() method is callable")
    
    print("All tests passed!")
