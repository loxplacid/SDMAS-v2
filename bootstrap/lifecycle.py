"""
Lifecycle management for application states.
"""

from enum import Enum
from typing import Dict, Any
import logging


class ApplicationState(Enum):
    """Enumeration of possible application states."""
    STOPPED = "stopped"
    STARTUP = "startup"
    RUNNING = "running"
    SHUTDOWN = "shutdown"
    RESTART = "restart"
    MAINTENANCE = "maintenance"


class LifecycleManager:
    """
    Manages the application lifecycle states.
    
    This class handles state transitions for the application including
    startup, running, shutdown, restart, and maintenance modes.
    """

    def __init__(self):
        self._current_state: ApplicationState = ApplicationState.STOPPED
        self._state_history: list = []
        
    @property
    def current_state(self) -> ApplicationState:
        """
        Get the current application state.
        
        Returns:
            ApplicationState: The current state of the application.
        """
        return self._current_state
    
    def set_state(self, new_state: str) -> None:
        """
        Set a new application state.
        
        Args:
            new_state (str): The name of the new state to transition to.
            
        Raises:
            ValueError: If the provided state is not valid.
        """
        try:
            # Convert string to enum
            state_enum = ApplicationState(new_state)
            
            # Log state change
            logging.info(f"Transitioning from {self._current_state.value} "
                        f"to {state_enum.value}")
            
            # Update history
            self._state_history.append(self._current_state)
            
            # Set new current state
            self._current_state = state_enum
            
        except ValueError:
            raise ValueError(f"Invalid application state: {new_state}")
    
    def get_state(self) -> ApplicationState:
        """
        Get the current application state.
        
        Returns:
            ApplicationState: The current state of the application.
        """
        return self._current_state
    
    def is_running(self) -> bool:
        """
        Check if the application is currently running.
        
        Returns:
            bool: True if the application is in 'running' state, False otherwise.
        """
        return self._current_state == ApplicationState.RUNNING
    
    def is_stopped(self) -> bool:
        """
        Check if the application is stopped.
        
        Returns:
            bool: True if the application is in 'stopped' state, False otherwise.
        """
        return self._current_state == ApplicationState.STOPPED
