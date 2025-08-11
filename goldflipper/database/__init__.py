"""
Database Package for Goldflipper
===============================

This package implements the database layer for the Goldflipper trading system using DuckDB.
DuckDB was chosen for its excellent performance characteristics and embedded nature, making
it perfect for our use case where we need both transactional and analytical capabilities.

Package Structure
---------------
- connection.py: Database connection management and initialization
- models.py: SQLAlchemy models representing database entities
- repositories.py: Repository pattern implementation for database operations
- migrations/: Database migration tools and scripts

Key Components
------------
1. Database Connection:
   - Managed through SQLAlchemy for better abstraction
   - Connection pooling for efficient resource usage
   - Automatic connection cleanup

2. Models:
   - Play: Represents an options trading play
   - PlayStatusHistory: Tracks status changes of plays
   - TradeLog: Records trade execution details
   - TradingStrategy: Defines trading strategies and parameters
   - ServiceBackup: Stores service state backups
   - LogEntry: Structured logging entries
   - ConfigTemplate: Configuration templates and validation
   - WatchdogEvent: System monitoring events
   - ChartConfiguration: Chart settings and preferences
   - ToolState: Tool state and configuration management

3. Repositories:
   - Implements repository pattern for clean data access
   - Handles CRUD operations
   - Provides specialized queries for common operations

Usage
-----
Basic usage example:
```python
from goldflipper.database import get_db_connection, PlayRepository

# Initialize database
init_db()

# Use repositories for data access
play_repo = PlayRepository()
active_plays = play_repo.get_active_plays()
```

Migration
--------
To migrate existing data from JSON files to the database:
```bash
poetry run goldflipper-migrate
```

Dependencies
-----------
- DuckDB: Embedded analytical database
- SQLAlchemy: ORM and database toolkit
- Alembic: Database migration tool
"""

from .connection import get_db_connection, init_db
from .models import (
    Play, 
    TradeLog, 
    PlayStatusHistory, 
    TradingStrategy, 
    ServiceBackup,
    LogEntry,
    ConfigTemplate,
    WatchdogEvent,
    ChartConfiguration,
    ToolState
)
from .repositories import (
    PlayRepository, 
    TradeLogRepository, 
    PlayStatusHistoryRepository,
    TradingStrategyRepository,
    ServiceBackupRepository,
    LogEntryRepository,
    ConfigTemplateRepository,
    WatchdogEventRepository,
    ChartConfigurationRepository,
    ToolStateRepository
)

__all__ = [
    'get_db_connection',
    'init_db',
    'Play',
    'TradeLog',
    'PlayStatusHistory',
    'TradingStrategy',
    'ServiceBackup',
    'LogEntry',
    'ConfigTemplate',
    'WatchdogEvent',
    'ChartConfiguration',
    'ToolState',
    'PlayRepository',
    'TradeLogRepository',
    'PlayStatusHistoryRepository',
    'TradingStrategyRepository',
    'ServiceBackupRepository',
    'LogEntryRepository',
    'ConfigTemplateRepository',
    'WatchdogEventRepository',
    'ChartConfigurationRepository',
    'ToolStateRepository',
] 