"""
Migration script to add market data and system-related tables.

This migration adds tables for:
1. Market data storage
2. User settings
3. System state
4. Analytics
"""

from datetime import datetime
from typing import Dict, Any
import logging

from sqlalchemy import (Boolean, Column, DateTime, Float, Index, Integer, JSON,
                       String, Table, UniqueConstraint, MetaData)
from sqlalchemy.exc import SQLAlchemyError

from ..connection import get_db_connection
from ..models import SQLUUID

logger = logging.getLogger(__name__)

metadata = MetaData()

# Market Data table
market_data = Table(
    'market_data',
    metadata,
    Column('id', SQLUUID, primary_key=True),
    Column('symbol', String, nullable=False),
    Column('timestamp', DateTime, nullable=False),
    Column('open', Float),
    Column('high', Float),
    Column('low', Float),
    Column('close', Float),
    Column('volume', Integer),
    Column('source', String),
    Column('implied_volatility', Float),
    Column('open_interest', Integer),
    Column('delta', Float),
    Column('gamma', Float),
    Column('theta', Float),
    Column('vega', Float),
    Index('idx_market_data_symbol_timestamp', 'symbol', 'timestamp')
)

# User Settings table
user_settings = Table(
    'user_settings',
    metadata,
    Column('id', SQLUUID, primary_key=True),
    Column('category', String, nullable=False),
    Column('key', String, nullable=False),
    Column('value', JSON),
    Column('last_modified', DateTime, default=datetime.utcnow),
    UniqueConstraint('category', 'key', name='unique_setting')
)

# System State table
system_state = Table(
    'system_state',
    metadata,
    Column('id', SQLUUID, primary_key=True),
    Column('component', String, nullable=False),
    Column('state', JSON),
    Column('timestamp', DateTime, default=datetime.utcnow),
    Column('is_active', Boolean, default=True)
)

# Analytics table
analytics = Table(
    'analytics',
    metadata,
    Column('id', SQLUUID, primary_key=True),
    Column('category', String, nullable=False),
    Column('metric', String, nullable=False),
    Column('value', Float),
    Column('timestamp', DateTime, default=datetime.utcnow),
    Column('metadata', JSON)
)

def upgrade() -> None:
    """
    Upgrade database schema by adding new tables.
    """
    try:
        with get_db_connection() as session:
            # Create tables
            metadata.create_all(session.bind)
            
            # Add default settings
            _add_default_settings(session)
            
            logger.info("Successfully added market data and system tables")
            
    except SQLAlchemyError as e:
        logger.error(f"Error during upgrade: {e}")
        raise

def downgrade() -> None:
    """
    Downgrade database schema by removing added tables.
    """
    try:
        with get_db_connection() as session:
            # Drop tables in reverse dependency order
            metadata.drop_all(session.bind)
            logger.info("Successfully removed market data and system tables")
            
    except SQLAlchemyError as e:
        logger.error(f"Error during downgrade: {e}")
        raise

def _add_default_settings(session) -> None:
    """Add default system settings."""
    default_settings: Dict[str, Dict[str, Any]] = {
        'trading': {
            'max_position_size': 5,
            'default_stop_loss': 0.10,
            'default_take_profit': 0.20,
            'risk_per_trade': 0.02
        },
        'market_data': {
            'update_interval': 60,
            'symbols': ['SPY', 'QQQ', 'IWM'],
            'data_retention_days': 30
        },
        'ui': {
            'theme': 'dark',
            'refresh_rate': 5,
            'chart_timeframe': '1D'
        },
        'alerts': {
            'email_enabled': False,
            'slack_enabled': False,
            'notification_level': 'INFO'
        }
    }
    
    try:
        for category, settings in default_settings.items():
            for key, value in settings.items():
                session.execute(
                    user_settings.insert().values(
                        category=category,
                        key=key,
                        value=value,
                        last_modified=datetime.utcnow()
                    )
                )
        logger.info("Successfully added default settings")
        
    except SQLAlchemyError as e:
        logger.error(f"Error adding default settings: {e}")
        raise 