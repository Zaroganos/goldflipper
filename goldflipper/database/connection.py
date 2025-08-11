"""
Database Connection Management for Goldflipper
=========================================

This module handles database connection management and initialization for the
Goldflipper trading system. It provides a robust connection pool, transaction
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
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from .models import Base

# Optional imports for resolving application version dynamically
try:
    from importlib.metadata import PackageNotFoundError, version as get_dist_version  # Python 3.8+
except Exception:  # pragma: no cover - compatibility fallback (not expected on >=3.11)
    get_dist_version = None
    PackageNotFoundError = Exception

try:  # Python 3.11+
    import tomllib  # type: ignore
except Exception:  # pragma: no cover
    tomllib = None

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
        """Initialize database configuration using OS-standard default with env override."""
        # Resolve repository root: .../goldflipper/goldflipper/database -> parents[3]
        repo_root = Path(__file__).resolve().parents[3]

        # Determine base data directory (environment variable overrides default)
        env_dir = os.getenv('GOLDFLIPPER_DATA_DIR')
        if env_dir:
            base_dir = Path(env_dir)
            if not base_dir.is_absolute():
                base_dir = (repo_root / base_dir).resolve()
        else:
            base_dir = self._get_default_base_dir()

        self._repo_root = repo_root
        self.base_dir = base_dir

        # Ensure base directory exists
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Set up database paths
        self.db_path = self.base_dir / 'db' / 'goldflipper.db'
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Set up backup directory
        self.backup_dir = self.base_dir / 'db' / 'backups'
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Set up temp directory
        self.temp_dir = self.base_dir / 'db' / 'temp'
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Connection pool configuration
        self.pool_size = int(os.getenv('GOLDFLIPPER_DB_POOL_SIZE', '5'))
        self.pool_timeout = int(os.getenv('GOLDFLIPPER_DB_TIMEOUT', '30'))

    def _get_default_base_dir(self) -> Path:
        """Return OS-appropriate default base directory for Goldflipper data.

        Windows: %LOCALAPPDATA%\Goldflipper
        macOS:   ~/Library/Application Support/Goldflipper
        Linux:   $XDG_DATA_HOME/goldflipper or ~/.local/share/goldflipper
        """
        try:
            if sys.platform.startswith('win'):
                local_appdata = os.getenv('LOCALAPPDATA')
                if not local_appdata:
                    # Fallback if LOCALAPPDATA not defined
                    local_appdata = str(Path.home() / 'AppData' / 'Local')
                return Path(local_appdata) / 'Goldflipper'
            elif sys.platform == 'darwin':
                return Path.home() / 'Library' / 'Application Support' / 'Goldflipper'
            else:
                xdg_data_home = os.getenv('XDG_DATA_HOME')
                if xdg_data_home:
                    return Path(xdg_data_home) / 'goldflipper'
                return Path.home() / '.local' / 'share' / 'goldflipper'
        except Exception:
            # Ultimate fallback to repository-relative data directory
            return (self._repo_root / 'data').resolve()

    def update_base_dir(self, new_base_dir: str) -> None:
        """Update the base data directory and refresh path attributes."""
        base = Path(new_base_dir)
        if not base.is_absolute():
            base = (self._repo_root / base).resolve()
        base.mkdir(parents=True, exist_ok=True)
        self.base_dir = base
        # Update paths
        self.db_path = self.base_dir / 'db' / 'goldflipper.db'
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_dir = self.base_dir / 'db' / 'backups'
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = self.base_dir / 'db' / 'temp'
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
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

def set_data_dir(new_base_dir: str) -> None:
    """Reconfigure the database base directory at runtime.

    Disposes existing engine, updates config paths, and resets engine singleton.
    """
    global _engine
    if _engine is not None:
        try:
            _engine.dispose()
        except Exception:
            pass
        _engine = None
    # Update config and environment for current process
    config.update_base_dir(new_base_dir)
    os.environ['GOLDFLIPPER_DATA_DIR'] = str(config.base_dir)

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
        # Resolve application version for User-Agent
        app_version = _resolve_app_version(config._repo_root)
        _engine = create_engine(
            config.connection_url,
            poolclass=QueuePool,
            pool_size=config.pool_size,
            pool_timeout=config.pool_timeout,
            # DuckDB specific settings for multi-process support
            connect_args={
                'database': str(config.db_path),
                'config': {
                    'custom_user_agent': f'goldflipper/{app_version}',
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


def _resolve_app_version(repo_root: Path) -> str:
    """Resolve the application version from installed metadata or pyproject.

    Tries distribution metadata first; falls back to reading pyproject.toml.
    Returns '0.0.0' if no version could be determined.
    """
    # 1) Try installed distributions (Poetry install)
    possible_names = (
        'goldflipper',
        'goldflipper-1.5',  # current project name in pyproject
    )
    if get_dist_version is not None:
        for dist_name in possible_names:
            try:
                return get_dist_version(dist_name)
            except PackageNotFoundError:
                continue

    # 2) Try reading pyproject.toml from repo
    pyproject_path = repo_root / 'goldflipper' / 'pyproject.toml'
    if tomllib is not None and pyproject_path.exists():
        try:
            with pyproject_path.open('rb') as f:
                data = tomllib.load(f)
            version_str = (
                data.get('tool', {})
                    .get('poetry', {})
                    .get('version')
            )
            if isinstance(version_str, str) and version_str.strip():
                return version_str.strip()
        except Exception:
            pass

    # 3) Last-resort fallback
    return '0.0.0'

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
    
    # Standard table creation approach is more reliable for DuckDB
    if force:
        logger.info("Dropping all existing tables")
        Base.metadata.drop_all(engine)
        logger.info("All tables dropped")
    
    # Standard table creation (will skip existing tables)
    Base.metadata.create_all(engine)
    
    # Optimize tables using DuckDB's PRAGMA
    with get_db_connection() as session:
        try:
            # Enable automatic statistics gathering
            session.execute(text("SET enable_progress_bar=false;"))
            session.execute(text("SET enable_object_cache=true;"))
            # Note: skip enable_external_access as it can't be changed while database is running
            # Force statistics collection for better query planning
            # Note: force_index_statistics doesn't exist in this DuckDB version
            # session.execute(text("PRAGMA force_index_statistics;"))
            logger.info("Database optimization completed")
        except Exception as e:
            logger.warning(f"Database optimization failed (non-critical): {str(e)}")
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