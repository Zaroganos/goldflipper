"""
Migration to add settings schema and migrate existing settings from YAML.

This migration:
1. Creates the settings_schema table
2. Adds the schema for all our settings
3. Migrates existing settings from settings.yaml to DuckDB
"""

from datetime import datetime
import logging
import yaml
from pathlib import Path
from typing import Dict, Any
import uuid
import json

from sqlalchemy import (Column, DateTime, JSON, String, Table, MetaData, text, UniqueConstraint)
from sqlalchemy.exc import SQLAlchemyError

from ..connection import get_db_connection
from ..models import SQLUUID

logger = logging.getLogger(__name__)

metadata = MetaData()

# Settings Schema table
settings_schema = Table(
    'settings_schema',
    metadata,
    Column('id', SQLUUID, primary_key=True),
    Column('category', String, nullable=False, unique=True),
    Column('schema', JSON, nullable=False),  # JSON Schema for validation
    Column('ui_schema', JSON),               # UI rendering hints
    Column('last_modified', DateTime, default=datetime.utcnow)
)

# User Settings table
user_settings = Table(
    'user_settings',
    metadata,
    Column('id', SQLUUID, primary_key=True),
    Column('category', String, nullable=False),
    Column('key', String, nullable=False),
    Column('value', JSON, nullable=False),
    Column('last_modified', DateTime, default=datetime.utcnow),
    UniqueConstraint('category', 'key', name='uix_category_key')
)

def load_yaml_settings() -> Dict[str, Any]:
    """Load settings from YAML file."""
    try:
        # Get absolute paths for better debugging
        current_file = Path(__file__).resolve()
        logger.info(f"Current file (absolute): {current_file}")
        
        # Try multiple possible paths
        possible_paths = [
            # From migration script location, go up to project root
            current_file.parent.parent.parent.parent / 'goldflipper' / 'config' / 'settings.yaml',
            # From workspace root
            Path.cwd() / 'goldflipper' / 'goldflipper' / 'config' / 'settings.yaml',
            # Direct from workspace root
            Path.cwd() / 'goldflipper' / 'config' / 'settings.yaml'
        ]
        
        logger.info("Checking possible paths for settings.yaml:")
        for path in possible_paths:
            logger.info(f"Trying path: {path} (exists: {path.exists()})")
            if path.exists():
                logger.info(f"Found settings.yaml at: {path}")
                with open(path, 'r') as f:
                    settings = yaml.safe_load(f)
                    if settings is None:
                        logger.error("YAML file loaded but returned None - might be empty or malformed")
                        continue
                    logger.info(f"Successfully loaded settings with {len(settings)} top-level keys")
                    logger.debug(f"Top-level keys: {list(settings.keys())}")
                    return settings
        
        logger.error("Could not find settings.yaml in any of the expected locations")
        return {}
            
    except Exception as e:
        logger.error(f"Error loading settings.yaml: {str(e)}", exc_info=True)
        return {}

# Define settings schemas
settings_schemas = {
    'logging': {
        'type': 'object',
        'properties': {
            'global': {
                'type': 'object',
                'properties': {
                    'level': {'type': 'string', 'enum': ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']},
                    'format': {'type': 'string'},
                    'file_rotation': {'type': 'boolean'},
                    'max_file_size_mb': {'type': 'integer', 'minimum': 1},
                    'backup_count': {'type': 'integer', 'minimum': 1},
                    'console_output': {'type': 'boolean'}
                }
            },
            'modules': {
                'type': 'object',
                'properties': {
                    'wem': {'$ref': '#/definitions/module_settings'},
                    'market_data': {'$ref': '#/definitions/module_settings'},
                    'trading': {'$ref': '#/definitions/module_settings'},
                    'database': {'$ref': '#/definitions/module_settings'},
                    'plays': {'$ref': '#/definitions/module_settings'}
                }
            }
        },
        'definitions': {
            'module_settings': {
                'type': 'object',
                'properties': {
                    'level': {'type': 'string', 'enum': ['INHERIT', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']},
                    'format': {'type': 'string'},
                    'file': {'type': 'string'},
                    'debug_file': {'type': 'string'}
                }
            }
        }
    },
    'wem': {
        'type': 'object',
        'properties': {
            'update_frequency': {'type': 'string', 'enum': ['hourly', 'daily', 'weekly']},
            'calculation_method': {'type': 'string', 'enum': ['standard', 'advanced', 'custom']},
            'confidence_threshold': {'type': 'integer', 'minimum': 0, 'maximum': 100},
            'max_stocks': {'type': 'integer', 'minimum': 1},
            'auto_update': {'type': 'boolean'}
        }
    },
    'market_data': {
        'type': 'object',
        'properties': {
            'providers': {
                'type': 'object',
                'properties': {
                    'marketdataapp': {
                        'type': 'object',
                        'properties': {
                            'enabled': {'type': 'boolean'},
                            'api_key': {'type': 'string'}
                        }
                    },
                    'alpaca': {
                        'type': 'object',
                        'properties': {
                            'enabled': {'type': 'boolean'},
                            'use_websocket': {'type': 'boolean'}
                        }
                    },
                    'yfinance': {
                        'type': 'object',
                        'properties': {
                            'enabled': {'type': 'boolean'}
                        }
                    }
                }
            }
        }
    }
}

# Add UI schema hints
ui_schemas = {
    'logging': {
        'ui:order': ['global', 'modules'],
        'global': {
            'ui:order': ['level', 'format', 'file_rotation', 'max_file_size_mb', 'backup_count', 'console_output']
        }
    },
    'wem': {
        'ui:order': ['update_frequency', 'calculation_method', 'confidence_threshold', 'max_stocks', 'auto_update']
    }
}

def flatten_settings(settings: dict, prefix: str = '') -> dict:
    """
    Recursively flatten a nested dictionary of settings.
    
    Args:
        settings (dict): The settings dictionary to flatten
        prefix (str): Current prefix for nested keys
        
    Returns:
        dict: Flattened dictionary with dot-separated keys
    """
    logger.info(f"Flattening settings with prefix: {prefix}")
    flattened = {}
    
    if not settings:
        logger.warning("Empty settings dictionary provided")
        return flattened
        
    for key, value in settings.items():
        # Skip comment keys
        if str(key).startswith('#'):
            logger.debug(f"Skipping comment key: {key}")
            continue
            
        # Skip None values
        if value is None:
            logger.debug(f"Skipping None value for key: {key}")
            continue
            
        # Create the full key path
        full_key = f"{prefix}.{key}" if prefix else key
        logger.debug(f"Processing key: {full_key}")
        
        if isinstance(value, dict):
            # Recursively flatten nested dictionaries
            logger.debug(f"Found nested dictionary at {full_key}")
            nested = flatten_settings(value, full_key)
            flattened.update(nested)
        else:
            # Convert non-string values to JSON
            if not isinstance(value, (str, int, float, bool)):
                logger.debug(f"Converting complex value to JSON for key: {full_key}")
                try:
                    value = json.dumps(value)
                except (TypeError, ValueError) as e:
                    logger.error(f"Failed to convert value for key {full_key}: {str(e)}")
                    continue
            
            logger.debug(f"Adding flattened setting: {full_key} = {value}")
            flattened[full_key] = value
    
    logger.info(f"Flattened {len(flattened)} settings")
    return flattened

def check_tables_exist(session) -> bool:
    """Check if required tables exist."""
    try:
        # Use a more reliable method to check if tables exist
        try:
            # Try to select from each table
            session.execute(text("SELECT 1 FROM settings_schema LIMIT 1")).fetchone()
            session.execute(text("SELECT 1 FROM user_settings LIMIT 1")).fetchone()
            logger.info("Both tables exist")
            return True
        except Exception:
            # If we got an exception, at least one table doesn't exist
            logger.info("At least one table is missing")
            return False
    except Exception as e:
        logger.error(f"Error checking tables: {str(e)}", exc_info=True)
        return False

def upgrade() -> None:
    """
    Upgrade database schema and migrate settings.
    """
    try:
        with get_db_connection() as session:
            logger.info("Starting database upgrade...")
            
            # Use direct SQL to create tables (more compatible with DuckDB)
            logger.info("Creating settings_schema table...")
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS settings_schema (
                    id VARCHAR PRIMARY KEY,
                    category VARCHAR UNIQUE NOT NULL,
                    schema VARCHAR,
                    ui_schema VARCHAR,
                    last_modified TIMESTAMP
                )
            """))
            
            logger.info("Creating user_settings table...")
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    id VARCHAR PRIMARY KEY,
                    category VARCHAR NOT NULL,
                    key VARCHAR,
                    value VARCHAR,
                    last_modified TIMESTAMP,
                    UNIQUE(category, key)
                )
            """))
            
            # Load settings from YAML
            logger.info("Loading settings from YAML...")
            yaml_settings = load_yaml_settings()
            if not yaml_settings:
                logger.error("No settings loaded from YAML")
                return
            logger.info(f"Loaded {len(yaml_settings)} top-level settings from YAML")
            
            # Add settings schema
            logger.info("Adding settings schemas...")
            for category, schema in settings_schemas.items():
                # First try to delete existing entry
                delete_query = text("DELETE FROM settings_schema WHERE category = :category")
                
                # Then insert new entry
                insert_query = text("""
                    INSERT INTO settings_schema (id, category, schema, ui_schema, last_modified)
                    VALUES (:id, :category, :schema, :ui_schema, :last_modified)
                """)
                
                try:
                    # Delete existing entry if any
                    session.execute(delete_query, {"category": category})
                    
                    # Insert new entry
                    session.execute(
                        insert_query,
                        {
                            "id": str(uuid.uuid4()),
                            "category": category,
                            "schema": json.dumps(schema),
                            "ui_schema": json.dumps(ui_schemas.get(category, {})),
                            "last_modified": datetime.utcnow().isoformat()
                        }
                    )
                    logger.info(f"Added schema for category: {category}")
                except Exception as e:
                    logger.error(f"Error adding schema for category {category}: {str(e)}")
                    raise
            
            # Migrate existing settings from YAML
            logger.info("Flattening settings...")
            flattened = flatten_settings(yaml_settings)
            logger.info(f"Found {len(flattened)} settings to import")
            
            # Print sample of flattened keys for debugging
            sample_keys = list(flattened.keys())[:5]
            logger.info(f"Sample flattened keys: {sample_keys}")
            
            # Process each setting individually
            imported_count = 0
            for key, value in flattened.items():
                try:
                    # Import all settings directly as top-level if no dot in key
                    if '.' not in key:
                        category = key
                        setting_key = ''
                    else:
                        # For dotted keys, first part is category, rest is the key
                        parts = key.split('.')
                        category = parts[0]
                        setting_key = '.'.join(parts[1:])
                    
                    logger.debug(f"Processing: key={key}, category={category}, setting_key={setting_key}")
                    
                    # Skip empty keys
                    if not category:
                        logger.warning(f"Skipping setting with empty category: {key}")
                        continue
                    
                    # Delete existing setting if any
                    session.execute(
                        text("DELETE FROM user_settings WHERE category = :category AND key = :key"),
                        {"category": category, "key": setting_key}
                    )
                    
                    # Insert new setting
                    session.execute(
                        text("INSERT INTO user_settings (id, category, key, value, last_modified) VALUES (:id, :category, :key, :value, :last_modified)"),
                        {
                            "id": str(uuid.uuid4()),
                            "category": category,
                            "key": setting_key,
                            "value": json.dumps(value) if not isinstance(value, str) else value,
                            "last_modified": datetime.utcnow().isoformat()
                        }
                    )
                    imported_count += 1
                    logger.debug(f"Imported setting: {category}.{setting_key}")
                except Exception as e:
                    logger.error(f"Error importing setting {key}: {str(e)}")
                    continue  # Continue with next setting instead of failing completely
            
            logger.info(f"Successfully imported {imported_count} settings")
            
            # Commit all changes
            logger.info("Committing changes...")
            session.commit()
            logger.info("Database upgrade completed successfully")
            
    except SQLAlchemyError as e:
        logger.error(f"Error during upgrade: {str(e)}", exc_info=True)
        raise

def downgrade() -> None:
    """
    Downgrade database schema by removing settings schema.
    """
    try:
        with get_db_connection() as session:
            metadata.drop_all(session.bind)
            logger.info("Successfully removed settings schema")
            
    except SQLAlchemyError as e:
        logger.error(f"Error during downgrade: {e}")
        raise 