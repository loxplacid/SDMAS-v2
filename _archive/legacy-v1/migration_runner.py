import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import os

logger = logging.getLogger(__name__)

class MigrationRunner(ABC):
    """Abstract base class for migration execution."""
    
    @abstractmethod
    def run_migrations(self) -> None:
        """Run all pending migrations."""
        pass
    
    @abstractmethod
    def get_pending_migrations(self) -> List[str]:
        """Get list of pending migrations."""
        pass

class SQLiteMigrationRunner(MigrationRunner):
    """SQLite migration runner implementation."""
    
    def __init__(self, database_path: str, migrations_dir: str = "migrations"):
        self.database_path = database_path
        self.migrations_dir = migrations_dir
    
    def run_migrations(self) -> None:
        """Run all pending SQLite migrations."""
        try:
            import sqlite3
            
            # Create migration table if it doesn't exist
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Get list of already applied migrations
            cursor.execute("SELECT name FROM migrations ORDER BY applied_at")
            applied_migrations = {row[0] for row in cursor.fetchall()}
            
            conn.close()
            
            # Get all migration files
            if not os.path.exists(self.migrations_dir):
                logger.warning(f"Migrations directory does not exist: {self.migrations_dir}")
                return
            
            migrations = []
            for filename in sorted(os.listdir(self.migrations_dir)):
                if filename.endswith(".sql") and filename.startswith("migration_"):
                    migrations.append(filename)
            
            # Apply pending migrations
            for migration_file in migrations:
                if migration_file not in applied_migrations:
                    self._execute_migration(migration_file)
                    
        except Exception as e:
            logger.error(f"Failed to run SQLite migrations: {e}")
            raise
    
    def get_pending_migrations(self) -> List[str]:
        """Get list of pending SQLite migrations."""
        try:
            import sqlite3
            
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            # Get already applied migrations
            cursor.execute("SELECT name FROM migrations ORDER BY applied_at")
            applied_migrations = {row[0] for row in cursor.fetchall()}
            
            conn.close()
            
            # Get all migration files
            if not os.path.exists(self.migrations_dir):
                return []
            
            migrations = []
            for filename in sorted(os.listdir(self.migrations_dir)):
                if filename.endswith(".sql") and filename.startswith("migration_"):
                    migrations.append(filename)
            
            pending = [m for m in migrations if m not in applied_migrations]
            return pending
            
        except Exception as e:
            logger.error(f"Failed to get pending SQLite migrations: {e}")
            raise
    
    def _execute_migration(self, migration_file: str) -> None:
        """Execute a single migration file."""
        try:
            import sqlite3
            
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            with open(os.path.join(self.migrations_dir, migration_file), 'r') as f:
                sql_script = f.read()
                
                # Execute the SQL script
                cursor.executescript(sql_script)
                
                # Record that this migration was applied
                cursor.execute(
                    "INSERT INTO migrations (name) VALUES (?)",
                    (migration_file,)
                )
            
            conn.commit()
            conn.close()
            
            logger.info(f"Successfully executed migration: {migration_file}")
            
        except Exception as e:
            logger.error(f"Failed to execute migration {migration_file}: {e}")
            raise

class MySQLMigrationRunner(MigrationRunner):
    """MySQL migration runner implementation."""
    
    def __init__(self, host: str, port: int, user: str, password: str, database: str, 
                 migrations_dir: str = "migrations"):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.migrations_dir = migrations_dir
    
    def run_migrations(self) -> None:
        """Run all pending MySQL migrations."""
        try:
            import mysql.connector
            
            # Create migration table if it doesn't exist
            conn = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database
            )
            
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB
            """)
            
            # Get list of already applied migrations
            cursor.execute("SELECT name FROM migrations ORDER BY applied_at")
            applied_migrations = {row[0] for row in cursor.fetchall()}
            
            conn.close()
            
            # Get all migration files
            if not os.path.exists(self.migrations_dir):
                logger.warning(f"Migrations directory does not exist: {self.migrations_dir}")
                return
            
            migrations = []
            for filename in sorted(os.listdir(self.migrations_dir)):
                if filename.endswith(".sql") and filename.startswith("migration_"):
                    migrations.append(filename)
            
            # Apply pending migrations
            for migration_file in migrations:
                if migration_file not in applied_migrations:
                    self._execute_migration(migration_file)
                    
        except Exception as e:
            logger.error(f"Failed to run MySQL migrations: {e}")
            raise
    
    def get_pending_migrations(self) -> List[str]:
        """Get list of pending MySQL migrations."""
        try:
            import mysql.connector
            
            conn = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database
            )
            
            cursor = conn.cursor()
            
            # Get already applied migrations
            cursor.execute("SELECT name FROM migrations ORDER BY applied_at")
            applied_migrations = {row[0] for row in cursor.fetchall()}
            
            conn.close()
            
            # Get all migration files
            if not os.path.exists(self.migrations_dir):
                return []
            
            migrations = []
            for filename in sorted(os.listdir(self.migrations_dir)):
                if filename.endswith(".sql") and filename.startswith("migration_"):
                    migrations.append(filename)
            
            pending = [m for m in migrations if m not in applied_migrations]
            return pending
            
        except Exception as e:
            logger.error(f"Failed to get pending MySQL migrations: {e}")
            raise
    
    def _execute_migration(self, migration_file: str) -> None:
        """Execute a single migration file."""
        try:
            import mysql.connector
            
            conn = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database
            )
            
            cursor = conn.cursor()
            
            with open(os.path.join(self.migrations_dir, migration_file), 'r') as f:
                sql_script = f.read()
                
                # Execute the SQL script
                statements = sql_script.split(';')
                for statement in statements:
                    if statement.strip():
                        cursor.execute(statement)
                
                # Record that this migration was applied
                cursor.execute(
                    "INSERT INTO migrations (name) VALUES (%s)",
                    (migration_file,)
                )
            
            conn.commit()
            conn.close()
            
            logger.info(f"Successfully executed migration: {migration_file}")
            
        except Exception as e:
            logger.error(f"Failed to execute migration {migration_file}: {e}")
            raise
