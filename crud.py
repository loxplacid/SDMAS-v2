import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar, Generic

logger = logging.getLogger(__name__)

T = TypeVar('T')

class CRUDOperations(Generic[T], ABC):
    """Abstract base class for basic CRUD operations."""
    
    @abstractmethod
    def create(self, entity: T) -> T:
        """Create a new entity."""
        pass
    
    @abstractmethod
    def get_by_id(self, id: Any) -> Optional[T]:
        """Get an entity by its ID."""
        pass
    
    @abstractmethod
    def update(self, entity: T) -> T:
        """Update an existing entity."""
        pass
    
    @abstractmethod
    def delete(self, id: Any) -> bool:
        """Delete an entity by its ID."""
        pass
    
    @abstractmethod
    def list_all(self) -> List[T]:
        """Get all entities."""
        pass

class SQLiteCRUDOperations(CRUDOperations[T]):
    """SQLite CRUD operations implementation."""
    
    def __init__(self, table_name: str, provider: Any):
        self.table_name = table_name
        self.provider = provider
    
    def create(self, entity: T) -> T:
        """Create a new entity in the database."""
        try:
            # This would be implemented by specific repository classes
            pass
            
        except Exception as e:
            logger.error(f"Failed to create entity: {e}")
            raise
    
    def get_by_id(self, id: Any) -> Optional[T]:
        """Get an entity by its ID."""
        try:
            query = f"SELECT * FROM {self.table_name} WHERE id = ?"
            results = self.provider.execute_query(query, (id,))
            
            if results:
                return results[0]  # Return first result
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to get entity by ID: {e}")
            raise
    
    def update(self, entity: T) -> T:
        """Update an existing entity."""
        try:
            # This would be implemented by specific repository classes
            pass
            
        except Exception as e:
            logger.error(f"Failed to update entity: {e}")
            raise
    
    def delete(self, id: Any) -> bool:
        """Delete an entity by its ID."""
        try:
            query = f"DELETE FROM {self.table_name} WHERE id = ?"
            affected_rows = self.provider.execute_update(query, (id,))
            
            return affected_rows > 0
            
        except Exception as e:
            logger.error(f"Failed to delete entity: {e}")
            raise
    
    def list_all(self) -> List[T]:
        """Get all entities."""
        try:
            query = f"SELECT * FROM {self.table_name}"
            results = self.provider.execute_query(query)
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to list all entities: {e}")
            raise

class MySQLCRUDOperations(CRUDOperations[T]):
    """MySQL CRUD operations implementation."""
    
    def __init__(self, table_name: str, provider: Any):
        self.table_name = table_name
        self.provider = provider
    
    def create(self, entity: T) -> T:
        """Create a new entity in the database."""
        try:
            # This would be implemented by specific repository classes
            pass
            
        except Exception as e:
            logger.error(f"Failed to create entity: {e}")
            raise
    
    def get_by_id(self, id: Any) -> Optional[T]:
        """Get an entity by its ID."""
        try:
            query = f"SELECT * FROM {self.table_name} WHERE id = %s"
            results = self.provider.execute_query(query, (id,))
            
            if results:
                return results[0]  # Return first result
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to get entity by ID: {e}")
            raise
    
    def update(self, entity: T) -> T:
        """Update an existing entity."""
        try:
            # This would be implemented by specific repository classes
            pass
            
        except Exception as e:
            logger.error(f"Failed to update entity: {e}")
            raise
    
    def delete(self, id: Any) -> bool:
        """Delete an entity by its ID."""
        try:
            query = f"DELETE FROM {self.table_name} WHERE id = %s"
            affected_rows = self.provider.execute_update(query, (id,))
            
            return affected_rows > 0
            
        except Exception as e:
            logger.error(f"Failed to delete entity: {e}")
            raise
    
    def list_all(self) -> List[T]:
        """Get all entities."""
        try:
            query = f"SELECT * FROM {self.table_name}"
            results = self.provider.execute_query(query)
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to list all entities: {e}")
            raise
