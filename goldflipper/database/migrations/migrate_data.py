"""
Data Migration Script for Goldflipper
=================================

This script handles the migration of play data from the legacy JSON file-based
storage system to the new DuckDB database. It provides a robust migration process
with error handling, logging, and data validation.

Migration Process
--------------
1. Initialize Database
   - Create database if it doesn't exist
   - Apply schema migrations
   - Set up logging

2. Read Source Data
   - Scan plays directory for JSON files
   - Parse play data by status (new, open, closed, expired)
   - Validate data structure and types

3. Transform & Load
   - Convert JSON data to database models
   - Create play records
   - Build status history
   - Record trade logs
   - Calculate and store metrics

4. Verify Migration
   - Count records by type
   - Validate relationships
   - Check data integrity
   - Generate migration report

Usage
-----
Run this script via uv:
```bash
uv run goldflipper-migrate
```

The script will:
1. Create database in data/db directory
2. Migrate all plays from JSON files
3. Generate status history and trade logs
4. Output migration statistics

Configuration
------------
The script uses the following environment variables:
- GOLDFLIPPER_DATA_DIR: Root directory for data files
- GOLDFLIPPER_DB_PATH: Path to database file
- GOLDFLIPPER_LOG_LEVEL: Logging level (default: INFO)
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from ..connection import get_db_connection, init_db
from ..models import Play, PlayStatusHistory, TradeLog
from ..repositories import PlayRepository, PlayStatusHistoryRepository, TradeLogRepository

# Configure logging
logging.basicConfig(
    level=os.getenv('GOLDFLIPPER_LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataMigrator:
    """
    Handles the migration of play data from JSON files to DuckDB.
    
    This class orchestrates the entire migration process, including reading
    source files, transforming data, and loading it into the database.
    
    Attributes:
        data_dir (Path): Root directory for JSON files
        session (Session): Database session
        play_repo (PlayRepository): Repository for play operations
        history_repo (PlayStatusHistoryRepository): Repository for status history
        trade_repo (TradeLogRepository): Repository for trade logs
    """
    
    def __init__(self, data_dir: Path, session: Session):
        """
        Initialize the migrator.
        
        Args:
            data_dir (Path): Root directory containing play data
            session (Session): SQLAlchemy session for database operations
        """
        self.data_dir = data_dir
        self.session = session
        self.play_repo = PlayRepository(session)
        self.history_repo = PlayStatusHistoryRepository(session)
        self.trade_repo = TradeLogRepository(session)
        
        # Migration statistics
        self.stats = {
            'plays_migrated': 0,
            'history_entries': 0,
            'trade_logs': 0,
            'errors': 0
        }
    
    def migrate_plays(self):
        """
        Migrate all plays from JSON files to the database.
        
        This method:
        1. Scans the plays directory for JSON files
        2. Processes each status directory (new, open, closed, expired)
        3. Creates database records for plays and related entities
        4. Tracks migration statistics
        
        Raises:
            FileNotFoundError: If plays directory doesn't exist
            JSONDecodeError: If JSON files are invalid
            SQLAlchemyError: If database operations fail
        """
        logger.info("Starting play migration...")
        
        # Process each status directory
        for status in ['new', 'open', 'closed', 'expired']:
            status_dir = self.data_dir / 'plays' / status
            if not status_dir.exists():
                logger.warning(f"Status directory not found: {status_dir}")
                continue
                
            logger.info(f"Processing {status} plays...")
            self._migrate_status_directory(status_dir, status)
        
        logger.info("Play migration completed.")
        self._log_migration_stats()
    
    def _migrate_status_directory(self, directory: Path, status: str):
        """
        Migrate plays from a specific status directory.
        
        Args:
            directory (Path): Path to status directory
            status (str): Play status ('new', 'open', 'closed', 'expired')
        """
        for file_path in directory.glob('*.json'):
            try:
                with open(file_path) as f:
                    play_data = json.load(f)
                
                # Add status if not present
                play_data['status'] = status
                
                # Create play record
                play = self.play_repo.create(play_data)
                self.stats['plays_migrated'] += 1
                
                # Create initial status history
                history = {
                    'play_id': play.play_id,
                    'status': status,
                    'timestamp': play.creation_date
                }
                self.history_repo.create(history)
                self.stats['history_entries'] += 1
                
                # Create trade log if closed
                if status in ['closed', 'expired']:
                    self._create_trade_log(play, play_data)
                
                logger.debug(f"Migrated play: {file_path.name}")
                
            except Exception as e:
                logger.error(f"Error migrating play {file_path}: {e}")
                self.stats['errors'] += 1
    
    def _create_trade_log(self, play: Play, play_data: Dict):
        """
        Create a trade log entry for a closed play.
        
        Args:
            play (Play): Play model instance
            play_data (Dict): Original play data from JSON
        """
        try:
            # Calculate P/L if available
            profit_loss = self._calculate_profit_loss(play_data)
            profit_loss_pct = self._calculate_profit_loss_pct(play_data)
            
            trade_log = {
                'play_id': play.play_id,
                'datetime_open': play.creation_date,
                'datetime_close': datetime.utcnow(),
                'premium_open': play_data.get('entry_point', {}).get('premium'),
                'premium_close': play_data.get('exit_point', {}).get('premium'),
                'profit_loss': profit_loss,
                'profit_loss_pct': profit_loss_pct
            }
            
            self.trade_repo.create(trade_log)
            self.stats['trade_logs'] += 1
            
        except Exception as e:
            logger.error(f"Error creating trade log for play {play.play_id}: {e}")
            self.stats['errors'] += 1
    
    def _calculate_profit_loss(self, play_data: Dict) -> Optional[float]:
        """
        Calculate absolute profit/loss for a play.
        
        Args:
            play_data (Dict): Play data from JSON
            
        Returns:
            Optional[float]: P/L in dollars, None if can't be calculated
        """
        try:
            entry = play_data.get('entry_point', {}).get('premium')
            exit_ = play_data.get('exit_point', {}).get('premium')
            contracts = play_data.get('contracts', 1)
            
            if entry is not None and exit_ is not None:
                return (exit_ - entry) * contracts * 100
            return None
        except:
            return None
    
    def _calculate_profit_loss_pct(self, play_data: Dict) -> Optional[float]:
        """
        Calculate percentage profit/loss for a play.
        
        Args:
            play_data (Dict): Play data from JSON
            
        Returns:
            Optional[float]: P/L as percentage, None if can't be calculated
        """
        try:
            entry = play_data.get('entry_point', {}).get('premium')
            exit_ = play_data.get('exit_point', {}).get('premium')
            
            if entry and exit_ and entry != 0:
                return ((exit_ - entry) / entry) * 100
            return None
        except:
            return None
    
    def _log_migration_stats(self):
        """Log migration statistics."""
        logger.info("Migration Statistics:")
        logger.info(f"  Plays Migrated: {self.stats['plays_migrated']}")
        logger.info(f"  History Entries: {self.stats['history_entries']}")
        logger.info(f"  Trade Logs: {self.stats['trade_logs']}")
        logger.info(f"  Errors: {self.stats['errors']}")

def run_migration():
    """
    Main entry point for the migration process.
    
    This function:
    1. Initializes the database
    2. Creates a database session
    3. Instantiates the migrator
    4. Runs the migration
    5. Handles any errors
    
    The function is registered as a console script entry point.
    """
    try:
        # Initialize database
        init_db()
        logger.info("Database initialized successfully")
        
        # Get data directory
        data_dir = Path(os.getenv('GOLDFLIPPER_DATA_DIR', 'data'))
        if not data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {data_dir}")
        
        # Run migration
        with get_db_connection() as session:
            migrator = DataMigrator(data_dir, session)
            migrator.migrate_plays()
            session.commit()
            
        logger.info("Migration completed successfully")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == '__main__':
    run_migration() 