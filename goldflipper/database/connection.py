"""
Database Connection Management for GoldFlipper
=========================================

This module handles database connection management and initialization for the
GoldFlipper trading system. It provides a robust connection pool, transaction
management, and database setup functionality.

Key Features
----------
1. Connection Pool Management
   - SQLAlchemy Engine singleton
   - Connection pooling for performance
   - Automatic connection recycling

2. Transaction Management
   - Context manager for safe transactions
   - Automatic rollback on errors
   - Session cleanup

3. Database Initialization
   - Schema creation
   - Table management
   - Index optimization

4. Backup & Recovery
   - Database backup creation
   - Point-in-time recovery
   - Backup file management

Configuration
-----------
The module uses the following environment variables:
- GOLDFLIPPER_DB_PATH: Path to database file
- GOLDFLIPPER_DB_POOL_SIZE: Connection pool size (default: 5)
- GOLDFLIPPER_DB_TIMEOUT: Connection timeout in seconds (default: 30)

Usage Example
-----------
```python
from goldflipper.database.connection import get_db_connection

# Using context manager for automatic cleanup
with get_db_connection() as session:
    # Perform database operations
    session.execute("SELECT * FROM plays")
    
# Database is automatically initialized
init_db()

# Create a backup
backup_database()
```
"""

import logging
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from .models import Base

# Configure logging
logging.basicConfig(
    level=os.getenv('GOLDFLIPPER_LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseConfig:
    """
    Configuration management for database connections.
    
    This class manages database configuration settings and provides
    utility methods for file path management.
    
    Attributes:
        db_path (Path): Path to the database file
        pool_size (int): Size of the connection pool
        pool_timeout (int): Connection timeout in seconds
        backup_dir (Path): Directory for database backups
        temp_dir (Path): Directory for temporary files
    """
    
    def __init__(self):
        """Initialize database configuration from environment variables."""
        # Get data directory from environment or use default
        data_dir = Path(os.getenv('GOLDFLIPPER_DATA_DIR', 'data'))
        
        # Ensure data directory exists
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Set up database paths
        self.db_path = data_dir / 'db' / 'goldflipper.db'
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Set up backup directory
        self.backup_dir = data_dir / 'db' / 'backups'
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Set up temp directory
        self.temp_dir = data_dir / 'db' / 'temp'
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Connection pool configuration
        self.pool_size = int(os.getenv('GOLDFLIPPER_DB_POOL_SIZE', '5'))
        self.pool_timeout = int(os.getenv('GOLDFLIPPER_DB_TIMEOUT', '30'))
    
    @property
    def connection_url(self) -> str:
        """
        Get the database connection URL.
        
        Returns:
            str: DuckDB connection URL
        """
        # DuckDB doesn't use URLs, but we keep this for SQLAlchemy compatibility
        return "duckdb://"
    
    def get_backup_path(self) -> Path:
        """
        Generate a path for a new database backup.
        
        Returns:
            Path: Path where the backup should be stored
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return self.backup_dir / f"goldflipper_backup_{timestamp}.db"

# Global configuration instance
config = DatabaseConfig()

# Global engine instance
_engine: Optional[Engine] = None

def get_engine() -> Engine:
    """
    Get or create the SQLAlchemy engine instance.
    
    This function implements the singleton pattern for the database engine,
    ensuring only one connection pool is created.
    
    Returns:
        Engine: SQLAlchemy engine instance
        
    Raises:
        SQLAlchemyError: If engine creation fails
    """
    global _engine
    
    if _engine is None:
        logger.info("Creating new database engine")
        _engine = create_engine(
            config.connection_url,
            poolclass=QueuePool,
            pool_size=config.pool_size,
            pool_timeout=config.pool_timeout,
            # DuckDB specific settings for multi-process support
            connect_args={
                'database': str(config.db_path),
                'config': {
                    'custom_user_agent': 'goldflipper/0.1.2',
                    'access_mode': 'READ_WRITE',
                    'allow_unsigned_extensions': 'true',
                    'threads': config.pool_size,  # Use pool size for thread count
                    'memory_limit': '4GB',  # Reasonable default memory limit
                    'temp_directory': str(config.temp_dir)  # Use configured temp directory
                },
                'read_only': False
            }
        )
        
        # Set up engine event listeners
        @event.listens_for(_engine, 'connect')
        def on_connect(dbapi_connection, connection_record):
            logger.debug("New database connection established")
        
        @event.listens_for(_engine, 'checkout')
        def on_checkout(dbapi_connection, connection_record, connection_proxy):
            logger.debug("Database connection checked out from pool")
    
    return _engine

@contextmanager
def get_db_connection() -> Generator[Session, None, None]:
    """
    Get a database session using context management.
    
    This context manager ensures proper handling of database sessions,
    including automatic cleanup and error handling.
    
    Yields:
        Session: Active database session
        
    Raises:
        SQLAlchemyError: If session operations fail
    """
    engine = get_engine()
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    
    try:
        yield session
        session.commit()
    except Exception as e:
        logger.error(f"Database session error: {e}")
        session.rollback()
        raise
    finally:
        session.close()

def init_db(force: bool = False) -> None:
    """
    Initialize the database schema.
    
    This function creates all necessary database tables and indexes.
    If tables already exist, it will only create missing ones unless
    force is True.
    
    Args:
        force (bool): If True, drop and recreate all tables
        
    Raises:
        SQLAlchemyError: If schema creation fails
    """
    engine = get_engine()
    
    if force:
        logger.warning("Forcing database reinitialization")
        Base.metadata.drop_all(engine)
    
    logger.info("Creating database schema")
    
    # Execute direct SQL instead of relying on SQLAlchemy reflection
    # This ensures tables match exactly what's defined in the models
    if force:
        # For each table defined in the models
        for table in Base.metadata.sorted_tables:
            try:
                # Check if table exists
                exists = engine.dialect.has_table(engine, table.name)
                
                # If it exists, drop it first
                if exists:
                    logger.info(f"Dropping table {table.name}")
                    table.drop(engine)
                
                # Create the table fresh
                logger.info(f"Creating table {table.name}")
                table.create(engine)
            except Exception as e:
                logger.error(f"Error recreating {table.name}: {str(e)}")
                # Continue with next table
    
    # Standard table creation (will skip existing tables)
    Base.metadata.create_all(engine)
    
    # Optimize tables using DuckDB's PRAGMA
    with get_db_connection() as session:
        try:
            # Enable automatic statistics gathering
            session.execute(text("SET enable_progress_bar=false;"))
            session.execute(text("SET enable_object_cache=true;"))
            session.execute(text("SET enable_external_access=true;"))
            # Force statistics collection for better query planning
            session.execute(text("PRAGMA force_index_statistics;"))
        except Exception as e:
            logger.error(f"Failed to optimize database: {str(e)}")
            # This is non-fatal, continue

def backup_database() -> Path:
    """
    Create a backup of the current database.
    
    Returns:
        Path: Path to the created backup file
        
    Raises:
        IOError: If backup creation fails
    """
    backup_path = config.get_backup_path()
    
    try:
        # Ensure we have a clean session
        engine = get_engine()
        engine.dispose()
        
        # Copy database file
        import shutil
        shutil.copy2(config.db_path, backup_path)
        
        logger.info(f"Database backup created: {backup_path}")
        return backup_path
    
    except Exception as e:
        logger.error(f"Backup creation failed: {e}")
        raise

def restore_database(backup_path: Path) -> None:
    """
    Restore the database from a backup.
    
    Args:
        backup_path (Path): Path to the backup file to restore from
        
    Raises:
        FileNotFoundError: If backup file doesn't exist
        IOError: If restore operation fails
    """
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")
    
    try:
        # Ensure we have a clean session
        engine = get_engine()
        engine.dispose()
        
        # Copy backup file to database location
        import shutil
        shutil.copy2(backup_path, config.db_path)
        
        logger.info(f"Database restored from backup: {backup_path}")
        
    except Exception as e:
        logger.error(f"Database restore failed: {e}")
        raise 