"""
Bootstrapper module for orchestrating application startup.
"""

from typing import List, Callable
import logging

from .lifecycle import LifecycleManager


class Bootstrapper:
    """
    Orchestrates the application startup process.
    
    The bootstrapper is responsible for coordinating all startup activities
    without containing any business logic. It ensures deterministic startup order.
    """

    def __init__(self, lifecycle_manager: LifecycleManager):
        self.lifecycle_manager = lifecycle_manager
        self._startup_steps: List[Callable] = []
        
    def add_startup_step(self, step: Callable) -> None:
        """
        Add a startup step to the bootstrapping process.
        
        Args:
            step (Callable): A callable that performs one part of the startup.
        """
        self._startup_steps.append(step)
    
    def bootstrap(self) -> None:
        """
        Execute all registered startup steps in order.
        
        This method orchestrates the entire application startup sequence
        ensuring deterministic execution without business logic.
        """
        logging.info("Starting bootstrapping process...")
        
        # Set initial state
        self.lifecycle_manager.set_state('startup')
        
        try:
            for step in self._startup_steps:
                step()
                
            logging.info("Bootstrapping completed successfully.")
            
        except Exception as e:
            logging.error(f"Bootstrap failed: {e}")
            raise


# Example usage (not part of the actual implementation):
# def example_startup_step():
#     print("Executing startup step...")
