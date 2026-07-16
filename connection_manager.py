import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class ConnectionManager(ABC):
    """Abstract base class for connection management."""
    
    @abstractmethod
    def get_connection(self) -> Any:
        """Get a database connection."""
        pass
    
    @abstractmethod
    def close_connection(self) -> None:
        """Close the database connection."""
        pass

class SQLiteConnectionManager(ConnectionManager):
    """SQLite connection manager implementation."""
    
    def __init__(self, database_path: str):
        self.database_path = database_path
        self._connection = None
    
    def get_connection(self) -> Any:
        """Get a SQLite connection."""
        try:
            import sqlite3
            if not self._connection:
                self._connection = sqlite3.connect(self.database_path)
                logger.info(f"Connected to SQLite database: {self.database_path}")
            return self._connection
        except Exception as e:
            logger.error(f"Failed to connect to SQLite database: {e}")
            raise
    
    def close_connection(self) -> None:
        """Close the SQLite connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("SQLite connection closed")

class MySQLConnectionManager(ConnectionManager):
    """MySQL connection manager implementation."""
    
    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self._connection = None
    
    def get_connection(self) -> Any:
        """Get a MySQL connection."""
        try:
            import mysql.connector
            if not self._connection:
                self._connection = mysql.connector.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    database=self.database
                )
                logger.info(f"Connected to MySQL database: {self.database}")
            return self._connection
        except Exception as e:
            logger.error(f"Failed to connect to MySQL database: {e}")
            raise
    
    def close_connection(self) -> None:
        """Close the MySQL connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("MySQL connection closed")
