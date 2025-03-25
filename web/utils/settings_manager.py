"""
Settings Manager

This module handles the synchronization of settings between:
1. DuckDB (source of truth)
2. settings.yaml (legacy/backup format)
3. Streamlit UI

It ensures that settings are properly validated against their schema
and that all systems remain in sync.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from sqlalchemy.orm import Session
from sqlalchemy import text
import json
import uuid

logger = logging.getLogger(__name__)

class SettingsManager:
    def __init__(self, session: Session):
        self.session = session
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.settings_file = self.project_root / 'goldflipper' / 'config' / 'settings.yaml'
        logger.info(f"Settings file path: {self.settings_file}")
        logger.info(f"Settings file exists: {self.settings_file.exists()}")
    
    def get_settings(self, category: Optional[str] = None) -> Dict[str, Any]:
        """
        Get settings from DuckDB.
        
        Args:
            category: Optional category to filter by
            
        Returns:
            Dictionary of settings
        """
        try:
            query = text("""
                SELECT category, key, value
                FROM user_settings
                WHERE 1=1
            """)
            params = {}
            
            if category:
                query = text("""
                    SELECT category, key, value
                    FROM user_settings
                    WHERE category = :category
                """)
                params = {"category": category}
            
            results = self.session.execute(query, params).fetchall()
            
            # Convert flat results to nested structure
            settings = {}
            for row in results:
                cat, key, value = row
                if cat not in settings:
                    settings[cat] = {}
                
                # Handle nested keys (e.g., 'global.level' -> {'global': {'level': value}})
                current = settings[cat]
                if key:  # Skip empty keys
                    parts = key.split('.')
                    for part in parts[:-1]:
                        current = current.setdefault(part, {})
                    current[parts[-1]] = value
            
            return settings if not category else settings.get(category, {})
            
        except Exception as e:
            logger.error(f"Error getting settings: {str(e)}", exc_info=True)
            return {}
    
    def update_setting(self, category: str, key: str, value: Any) -> bool:
        """
        Update a single setting in DuckDB and sync to YAML.
        
        Args:
            category: Setting category (e.g., 'logging', 'wem')
            key: Setting key (can be nested, e.g., 'global.level')
            value: New value
            
        Returns:
            bool: Success status
        """
        try:
            # Update in DuckDB
            self.session.execute(
                text("""
                INSERT INTO user_settings (id, category, key, value, last_modified)
                VALUES (:id, :category, :key, :value, :last_modified)
                ON CONFLICT (category, key) DO UPDATE
                SET value = excluded.value, last_modified = excluded.last_modified
                """),
                {
                    "id": str(uuid.uuid4()),
                    "category": category,
                    "key": key,
                    "value": json.dumps(value) if not isinstance(value, str) else value,
                    "last_modified": datetime.utcnow().isoformat()
                }
            )
            self.session.commit()
            
            # Sync to YAML
            self._sync_to_yaml()
            
            logger.info(f"Updated setting {category}.{key} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating setting: {str(e)}", exc_info=True)
            return False
    
    def update_settings(self, settings: Dict[str, Any]) -> bool:
        """
        Update multiple settings at once.
        
        Args:
            settings: Dictionary of settings to update
            
        Returns:
            bool: Success status
        """
        try:
            # Flatten settings for DB storage
            logger.info("Flattening settings...")
            flattened = self._flatten_settings(settings)
            logger.info(f"Found {len(flattened)} settings to update")
            logger.debug("Flattened settings:")
            for (category, key), value in flattened.items():
                logger.debug(f"  {category}.{key} = {value}")
            
            # Update all settings in a transaction
            logger.info("Starting settings update transaction...")
            transaction_succeeded = True
            for (category, key), value in flattened.items():
                logger.debug(f"Updating {category}.{key}...")
                try:
                    self.session.execute(
                        text("""
                        INSERT INTO user_settings (id, category, key, value, last_modified)
                        VALUES (:id, :category, :key, :value, :last_modified)
                        ON CONFLICT (category, key) DO UPDATE
                        SET value = excluded.value, last_modified = excluded.last_modified
                        """),
                        {
                            "id": str(uuid.uuid4()),
                            "category": category,
                            "key": key,
                            "value": json.dumps(value) if not isinstance(value, str) else value,
                            "last_modified": datetime.utcnow().isoformat()
                        }
                    )
                    logger.debug(f"Successfully updated {category}.{key}")
                except Exception as e:
                    logger.error(f"Error updating {category}.{key}: {str(e)}")
                    transaction_succeeded = False
                    # Don't raise, we'll handle the error below
            
            if transaction_succeeded:
                logger.info("Committing transaction...")
                self.session.commit()
                
                # Sync to YAML
                logger.info("Syncing to YAML...")
                self._sync_to_yaml()
                
                logger.info("Successfully updated all settings")
                return True
            else:
                logger.error("Transaction failed, not committing changes")
                # Only try to rollback if the session has the method
                if hasattr(self.session, 'rollback'):
                    logger.info("Rolling back transaction...")
                    self.session.rollback()
                return False
            
        except Exception as e:
            logger.error(f"Error updating settings: {str(e)}", exc_info=True)
            # Only try to rollback if the session has the method
            if hasattr(self.session, 'rollback'):
                logger.info("Rolling back transaction...")
                self.session.rollback()
            return False
    
    def _flatten_settings(self, settings: Dict[str, Any], prefix: str = '') -> Dict[tuple, Any]:
        """Flatten nested settings dictionary."""
        flattened = {}
        for key, value in settings.items():
            # Skip comment keys (starting with #)
            if isinstance(key, str) and key.startswith('#'):
                continue
                
            # Skip None values
            if value is None:
                continue
                
            if isinstance(value, dict):
                # For nested dictionaries, use the current key as category if no prefix
                if not prefix:
                    # This is a top-level key (category)
                    nested = self._flatten_settings(value, key)
                    flattened.update(nested)
                else:
                    # This is a nested key
                    nested = self._flatten_settings(value, f"{prefix}.{key}")
                    flattened.update(nested)
            else:
                if not prefix:
                    # This is a top-level key-value pair
                    category = key
                    key_path = ''
                else:
                    # This is a nested key-value pair
                    parts = prefix.split('.')
                    category = parts[0]
                    key_path = '.'.join(parts[1:] + [key]) if len(parts) > 1 else key
                
                # Convert lists and other objects to JSON strings
                if isinstance(value, (list, dict)):
                    value = json.dumps(value)
                elif not isinstance(value, (str, int, float, bool)):
                    value = str(value)
                
                flattened[(category, key_path)] = value
        
        return flattened
    
    def _sync_to_yaml(self) -> bool:
        """Sync current settings to YAML file."""
        try:
            # Get all settings
            settings = self.get_settings()
            
            # Write to YAML
            with open(self.settings_file, 'w') as f:
                yaml.dump(settings, f, default_flow_style=False)
            
            logger.info("Successfully synced settings to YAML")
            return True
            
        except Exception as e:
            logger.error(f"Error syncing to YAML: {str(e)}", exc_info=True)
            return False
    
    def import_from_yaml(self) -> bool:
        """Import settings from YAML to DuckDB."""
        try:
            logger.info(f"Attempting to import settings from: {self.settings_file}")
            
            if not self.settings_file.exists():
                logger.warning(f"settings.yaml not found at: {self.settings_file}")
                return False
            
            # Load YAML
            logger.info("Reading YAML file...")
            with open(self.settings_file, 'r') as f:
                settings = yaml.safe_load(f)
            
            if settings is None:
                logger.error("YAML file is empty or invalid")
                return False
                
            logger.info(f"Loaded settings with {len(settings)} top-level keys")
            logger.debug(f"Top-level keys: {list(settings.keys())}")
            
            # Update settings
            logger.info("Updating settings in DuckDB...")
            success = self.update_settings(settings)
            
            if success:
                logger.info("Successfully imported settings from YAML")
            else:
                logger.error("Failed to update settings in DuckDB")
            
            return success
            
        except Exception as e:
            logger.error(f"Error importing from YAML: {str(e)}", exc_info=True)
            return False
    
    def get_schema(self, category: str) -> Dict[str, Any]:
        """
        Get JSON Schema for a settings category.
        
        Args:
            category: Settings category
            
        Returns:
            Dictionary containing the JSON Schema
        """
        try:
            result = self.session.execute(
                text("SELECT schema FROM settings_schema WHERE category = :category"),
                {"category": category}
            ).fetchone()
            
            return result[0] if result else {}
            
        except Exception as e:
            logger.error(f"Error getting schema: {str(e)}", exc_info=True)
            return {} 