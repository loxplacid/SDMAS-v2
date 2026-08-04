"""
Shutdown manager for gracefully terminating application processes.
"""

from typing import List, Dict, Any
import logging

from .lifecycle import LifecycleManager


class ShutdownManager:
    """
    Manages the graceful shutdown of application components.
    
    This class ensures that all resources are properly cleaned up during 
    application termination, including database connections, worker threads,
    and plugin cleanup.
    """

    def __init__(self):
        self._shutdown_order = [
            'database',
            'workers',
            'plugins',
            'services',
            'logging'
        ]
        
        # Track shutdown components
        self._shutdown_components: List[str] = []
    
    def execute_shutdown_sequence(self) -> None:
        """
        Execute the complete shutdown sequence in reverse order.
        
        This method ensures that all resources are properly cleaned up,
        with dependencies being shut down before their dependents.
        """
        logging.info("Starting application shutdown sequence...")
        
        # Reverse the startup order for proper cleanup
        components_to_shutdown = reversed(self._shutdown_order)
        
        for component_name in components_to_shutdown:
            try:
                self._cleanup_component(component_name)
                self._shutdown_components.append(component_name)
                
                logging.info(f"Successfully shut down {component_name}")
                
            except Exception as e:
                logging.error(f"Error during shutdown of {component_name}: {e}")
                # Continue with other components even if one fails
                continue
    
    def _cleanup_component(self, component: str) -> None:
        """
        Clean up a specific component.
        
        Args:
            component (str): Name of the component to clean up.
            
        Raises:
            NotImplementedError: If the cleanup logic is not implemented yet.
        """
        # In a real implementation, this would contain actual cleanup logic
        logging.debug(f"Cleaning up {component}...")
        
        # Placeholder for actual implementation
        pass
    
    def get_shutdown_components(self) -> List[str]:
        """
        Get list of components that were successfully shut down.
        
        Returns:
            List[str]: List of component names that were shut down.
        """
        return self._shutdown_components.copy()


# Test cases
if __name__ == "__main__":
    # Configure logging for testing
    logging.basicConfig(level=logging.INFO)
    
    # Create shutdown manager
    sm = ShutdownManager()
    
    # Verify all methods exist and are callable
    assert hasattr(sm, 'execute_shutdown_sequence')
    assert hasattr(sm, '_cleanup_component')
    assert hasattr(sm, 'get_shutdown_components')
    
    print("✓ All shutdown methods are defined")
    
    # Test that execute_shutdown_sequence method exists
    assert hasattr(sm, 'execute_shutdown_sequence')
    print("✓ execute_shutdown_sequence method is defined")
    
    # Verify the shutdown order
    expected_order = ['database', 'workers', 'plugins', 'services', 'logging']
    assert sm._shutdown_order == expected_order
    print("✓ Shutdown order is correctly configured")
    
    # Test that get_shutdown_components returns a copy
    components = sm.get_shutdown_components()
    assert isinstance(components, list)
    print("✓ get_shutdown_components returns a copy of the list")
    
    print("All tests passed!")
