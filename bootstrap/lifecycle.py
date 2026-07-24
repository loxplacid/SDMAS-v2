"""
Lifecycle management for application states.
"""

from enum import Enum
from typing import Dict, Any
import logging


class ApplicationState(Enum):
    """Enumeration of possible application states."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    RESTARTING = "restarting"
    FAILED = "failed"


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
    
    def is_starting(self) -> bool:
        """
        Check if the application is starting.
        
        Returns:
            bool: True if the application is in 'starting' state, False otherwise.
        """
        return self._current_state == ApplicationState.STARTING
    
    def is_stopping(self) -> bool:
        """
        Check if the application is stopping.
        
        Returns:
            bool: True if the application is in 'stopping' state, False otherwise.
        """
        return self._current_state == ApplicationState.STOPPING
    
    def is_restarting(self) -> bool:
        """
        Check if the application is restarting.
        
        Returns:
            bool: True if the application is in 'restarting' state, False otherwise.
        """
        return self._current_state == ApplicationState.RESTARTING
    
    def is_failed(self) -> bool:
        """
        Check if the application has failed.
        
        Returns:
            bool: True if the application is in 'failed' state, False otherwise.
        """
        return self._current_state == ApplicationState.FAILED

    def get_state_history(self) -> list:
        """
        Get the history of state transitions.
        
        Returns:
            list: A copy of the state transition history.
        """
        return self._state_history.copy()

    def reset_state_history(self) -> None:
        """
        Clear the state transition history.
        """
        self._state_history.clear()


# Test cases
if __name__ == "__main__":
    # Configure logging for testing
    logging.basicConfig(level=logging.INFO)
    
    # Create lifecycle manager
    lm = LifecycleManager()
    
    # Test initial state
    assert lm.current_state == ApplicationState.STOPPED
    print("✓ Initial state is STOPPED")
    
    # Test setting states
    lm.set_state("STARTING")
    assert lm.current_state == ApplicationState.STARTING
    print("✓ Can set STARTING state")
    
    lm.set_state("RUNNING")
    assert lm.current_state == ApplicationState.RUNNING
    print("✓ Can set RUNNING state")
    
    lm.set_state("STOPPING")
    assert lm.current_state == ApplicationState.STOPPING
    print("✓ Can set STOPPING state")
    
    lm.set_state("STOPPED")
    assert lm.current_state == ApplicationState.STOPPED
    print("✓ Can set STOPPED state")
    
    lm.set_state("RESTARTING")
    assert lm.current_state == ApplicationState.RESTARTING
    print("✓ Can set RESTARTING state")
    
    lm.set_state("FAILED")
    assert lm.current_state == ApplicationState.FAILED
    print("✓ Can set FAILED state")
    
    # Test boolean methods
    lm.set_state("RUNNING")
    assert lm.is_running() is True
    assert lm.is_stopped() is False
    print("✓ is_running() and is_stopped() work correctly")
    
    lm.set_state("STOPPED")
    assert lm.is_running() is False
    assert lm.is_stopped() is True
    print("✓ is_running() and is_stopped() work correctly for STOPPED state")
    
    # Test invalid state
    try:
        lm.set_state("INVALID_STATE")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"✓ Correctly rejects invalid state: {e}")
    
    print("All tests passed!")
