import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class PoolManager(ABC):
    """Abstract base class for pool management."""
    
    @abstractmethod
    def get_connection(self) -> Any:
        """Get a connection from the pool."""
        pass
    
    @abstractmethod
    def return_connection(self, connection: Any) -> None:
        """Return a connection to the pool."""
        pass

class SQLitePoolManager(PoolManager):
    """SQLite connection pool manager implementation."""
    
    def __init__(self, database_path: str, max_connections: int = 5):
        self.database_path = database_path
        self.max_connections = max_connections
        self._connections = []
        self._used_connections = set()
        
        # Initialize the pool with connections
        for _ in range(max_connections):
            import sqlite3
            conn = sqlite3.connect(database_path, check_same_thread=False)
            self._connections.append(conn)
    
    def get_connection(self) -> Any:
        """Get a connection from the SQLite pool."""
        try:
            if not self._connections:
                raise Exception("No available connections in pool")
            
            connection = self._connections.pop()
            self._used_connections.add(connection)
            logger.debug(f"Got connection from SQLite pool. Used: {len(self._used_connections)}")
            return connection
        except Exception as e:
            logger.error(f"Failed to get connection from SQLite pool: {e}")
            raise
    
    def return_connection(self, connection: Any) -> None:
        """Return a connection to the SQLite pool."""
        if connection in self._used_connections:
            self._used_connections.remove(connection)
            self._connections.append(connection)
            logger.debug(f"Returned connection to SQLite pool. Available: {len(self._connections)}")
        else:
            raise ValueError("Connection not from this pool")

class MySQLPoolManager(PoolManager):
    """MySQL connection pool manager implementation."""
    
    def __init__(self, host: str, port: int, user: str, password: str, database: str, 
                 max_connections: int = 10):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.max_connections = max_connections
        self._connections = []
        self._used_connections = set()
        
        # Initialize the pool with connections
        import mysql.connector.pooling
        self._pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="mypool",
            pool_size=max_connections,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
    
    def get_connection(self) -> Any:
        """Get a connection from the MySQL pool."""
        try:
            connection = self._pool.get_connection()
            self._used_connections.add(connection)
            logger.debug(f"Got connection from MySQL pool. Used: {len(self._used_connections)}")
            return connection
        except Exception as e:
            logger.error(f"Failed to get connection from MySQL pool: {e}")
            raise
    
    def return_connection(self, connection: Any) -> None:
        """Return a connection to the MySQL pool."""
        if connection in self._used_connections:
            connection.close()  # Return to pool
            self._used_connections.remove(connection)
            logger.debug(f"Returned connection to MySQL pool. Available: {len(self._connections)}")
        else:
            raise ValueError("Connection not from this pool")
