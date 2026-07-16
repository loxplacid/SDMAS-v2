import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class MySQLProvider(DatabaseProvider):
    """MySQL database provider implementation."""
    
    def __init__(self, connection_manager: Any):
        self.connection_manager = connection_manager
    
    @contextmanager
    def get_connection(self):
        """Context manager for getting a database connection."""
        conn = None
        try:
            conn = self.connection_manager.get_connection()
            yield conn
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            if conn:
                pass  # Connection is managed by the manager
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict]:
        """Execute a SELECT query and return results."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                result = cursor.fetchall()
                logger.debug(f"Query executed successfully: {query}")
                return result
                
        except Exception as e:
            logger.error(f"Failed to execute query: {e}")
            raise
    
    def execute_update(self, query: str, params: Optional[tuple] = None) -> int:
        """Execute an INSERT/UPDATE/DELETE query and return affected rows count."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                affected_rows = cursor.rowcount
                conn.commit()
                
                logger.debug(f"Update executed successfully: {query}")
                return affected_rows
                
        except Exception as e:
            logger.error(f"Failed to execute update: {e}")
            raise
