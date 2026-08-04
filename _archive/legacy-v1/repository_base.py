import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar, Generic
from contextlib import contextmanager

logger = logging.getLogger(__name__)

T = TypeVar('T')

class RepositoryBase(Generic[T], ABC):
    """Abstract base class for repositories."""
    
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

class SQLiteRepositoryBase(RepositoryBase[T]):
    """SQLite repository base implementation."""
    
    def __init__(self, table_name: str, provider: Any):
        self.table_name = table_name
        self.provider = provider
    
    @abstractmethod
    def _entity_to_dict(self, entity: T) -> Dict:
        """Convert an entity to a dictionary for database operations."""
        pass
    
    @abstractmethod
    def _dict_to_entity(self, data: Dict) -> T:
        """Convert a dictionary from database to an entity."""
        pass
    
    def create(self, entity: T) -> T:
        """Create a new entity in the database."""
        try:
            # Get column names and values
            entity_dict = self._entity_to_dict(entity)
            
            columns = list(entity_dict.keys())
            placeholders = ', '.join(['?' for _ in columns])
            query = f"INSERT INTO {self.table_name} ({', '.join(columns)}) VALUES ({placeholders})"
            
            # Execute the insert operation
            affected_rows = self.provider.execute_update(query, tuple(entity_dict.values()))
            
            if affected_rows > 0:
                logger.info(f"Created entity in table {self.table_name}")
                return entity
            else:
                raise Exception("Failed to create entity")
                
        except Exception as e:
            logger.error(f"Failed to create entity: {e}")
            raise
    
    def get_by_id(self, id: Any) -> Optional[T]:
        """Get an entity by its ID."""
        try:
            query = f"SELECT * FROM {self.table_name} WHERE id = ?"
            results = self.provider.execute_query(query, (id,))
            
            if results:
                return self._dict_to_entity(results[0])
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to get entity by ID: {e}")
            raise
    
    def update(self, entity: T) -> T:
        """Update an existing entity."""
        try:
            # Get column names and values
            entity_dict = self._entity_to_dict(entity)
            
            # Build SET clause for UPDATE query
            set_clause = ', '.join([f"{key} = ?" for key in entity_dict.keys()])
            query = f"UPDATE {self.table_name} SET {set_clause} WHERE id = ?"
            
            # Add the ID to the values tuple
            values = list(entity_dict.values()) + [entity_dict.get('id')]
            
            # Execute the update operation
            affected_rows = self.provider.execute_update(query, tuple(values))
            
            if affected_rows > 0:
                logger.info(f"Updated entity in table {self.table_name}")
                return entity
            else:
                raise Exception("Failed to update entity")
                
        except Exception as e:
            logger.error(f"Failed to update entity: {e}")
            raise
    
    def delete(self, id: Any) -> bool:
        """Delete an entity by its ID."""
        try:
            query = f"DELETE FROM {self.table_name} WHERE id = ?"
            affected_rows = self.provider.execute_update(query, (id,))
            
            if affected_rows > 0:
                logger.info(f"Deleted entity from table {self.table_name}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete entity: {e}")
            raise
    
    def list_all(self) -> List[T]:
        """Get all entities."""
        try:
            query = f"SELECT * FROM {self.table_name}"
            results = self.provider.execute_query(query)
            
            return [self._dict_to_entity(row) for row in results]
            
        except Exception as e:
            logger.error(f"Failed to list all entities: {e}")
            raise

class MySQLRepositoryBase(RepositoryBase[T]):
    """MySQL repository base implementation."""
    
    def __init__(self, table_name: str, provider: Any):
        self.table_name = table_name
        self.provider = provider
    
    @abstractmethod
    def _entity_to_dict(self, entity: T) -> Dict:
        """Convert an entity to a dictionary for database operations."""
        pass
    
    @abstractmethod
    def _dict_to_entity(self, data: Dict) -> T:
        """Convert a dictionary from database to an entity."""
        pass
    
    def create(self, entity: T) -> T:
        """Create a new entity in the database."""
        try:
            # Get column names and values
            entity_dict = self._entity_to_dict(entity)
            
            columns = list(entity_dict.keys())
            placeholders = ', '.join(['%s' for _ in columns])
            query = f"INSERT INTO {self.table_name} ({', '.join(columns)}) VALUES ({placeholders})"
            
            # Execute the insert operation
            affected_rows = self.provider.execute_update(query, tuple(entity_dict.values()))
            
            if affected_rows > 0:
                logger.info(f"Created entity in table {self.table_name}")
                return entity
            else:
                raise Exception("Failed to create entity")
                
        except Exception as e:
            logger.error(f"Failed to create entity: {e}")
            raise
    
    def get_by_id(self, id: Any) -> Optional[T]:
        """Get an entity by its ID."""
        try:
            query = f"SELECT * FROM {self.table_name} WHERE id = %s"
            results = self.provider.execute_query(query, (id,))
            
            if results:
                return self._dict_to_entity(results[0])
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to get entity by ID: {e}")
            raise
    
    def update(self, entity: T) -> T:
        """Update an existing entity."""
        try:
            # Get column names and values
            entity_dict = self._entity_to_dict(entity)
            
            # Build SET clause for UPDATE query
            set_clause = ', '.join([f"{key} = %s" for key in entity_dict.keys()])
            query = f"UPDATE {self.table_name} SET {set_clause} WHERE id = %s"
            
            # Add the ID to the values tuple
            values = list(entity_dict.values()) + [entity_dict.get('id')]
            
            # Execute the update operation
            affected_rows = self.provider.execute_update(query, tuple(values))
            
            if affected_rows > 0:
                logger.info(f"Updated entity in table {self.table_name}")
                return entity
            else:
                raise Exception("Failed to update entity")
                
        except Exception as e:
            logger.error(f"Failed to update entity: {e}")
            raise
    
    def delete(self, id: Any) -> bool:
        """Delete an entity by its ID."""
        try:
            query = f"DELETE FROM {self.table_name} WHERE id = %s"
            affected_rows = self.provider.execute_update(query, (id,))
            
            if affected_rows > 0:
                logger.info(f"Deleted entity from table {self.table_name}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete entity: {e}")
            raise
    
    def list_all(self) -> List[T]:
        """Get all entities."""
        try:
            query = f"SELECT * FROM {self.table_name}"
            results = self.provider.execute_query(query)
            
            return [self._dict_to_entity(row) for row in results]
            
        except Exception as e:
            logger.error(f"Failed to list all entities: {e}")
            raise
