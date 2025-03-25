"""
Settings Mapper Module

This module handles the mapping and synchronization between:
1. Streamlit UI paths/values
2. DuckDB tables/columns
3. YAML configuration file

The DuckDB database is treated as the source of truth, while the YAML file
serves as an export/import format and backup mechanism.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class SettingsMapper:
    """Maps between DuckDB, UI, and YAML representations of settings"""
    
    def __init__(self, session: Session):
        self.session = session
        # UI path -> DuckDB table.column mapping
        self.ui_to_db_map = {
            # Logging settings
            'logging.global.level': 'system_settings.log_level',
            'logging.global.format': 'system_settings.log_format',
            'logging.global.file_rotation': 'system_settings.log_rotation_enabled',
            'logging.global.max_file_size_mb': 'system_settings.log_max_file_size',
            'logging.global.backup_count': 'system_settings.log_backup_count',
            'logging.global.console_output': 'system_settings.log_console_output',
            
            # Module-specific logging
            'logging.modules.wem.level': 'module_settings.wem_log_level',
            'logging.modules.market_data.level': 'module_settings.market_data_log_level',
            'logging.modules.trading.level': 'module_settings.trading_log_level',
            'logging.modules.database.level': 'module_settings.database_log_level',
            'logging.modules.plays.level': 'module_settings.plays_log_level',
            
            # WEM settings
            'wem.update_frequency': 'wem_settings.update_freq',
            'wem.calculation_method': 'wem_settings.calc_method',
            'wem.confidence_threshold': 'wem_settings.confidence_threshold',
            'wem.max_stocks': 'wem_settings.max_stocks',
            'wem.auto_update': 'wem_settings.auto_update_enabled',
            
            # Market data provider settings
            'market_data.providers.marketdataapp.api_key': 'api_keys.marketdataapp',
            'market_data.providers.marketdataapp.enabled': 'provider_settings.marketdataapp_enabled',
            'market_data.providers.alpaca.enabled': 'provider_settings.alpaca_enabled',
            'market_data.providers.yfinance.enabled': 'provider_settings.yfinance_enabled'
        }
        
        # Reverse mapping for YAML export
        self.db_to_ui_map = {v: k for k, v in self.ui_to_db_map.items()}
    
    def get_setting(self, ui_path: str) -> Optional[Any]:
        """Get a setting value from DuckDB"""
        db_path = self.ui_to_db_map.get(ui_path)
        if not db_path:
            logger.warning(f"No DB mapping for UI setting: {ui_path}")
            return None
            
        table, column = db_path.split('.')
        try:
            result = self.session.execute(f"""
                SELECT {column} 
                FROM {table} 
                WHERE id = (SELECT MAX(id) FROM {table})
            """).fetchone()
            
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Failed to get setting {ui_path}: {str(e)}")
            return None
    
    def update_setting(self, ui_path: str, new_value: Any) -> bool:
        """Update a setting in DuckDB from UI"""
        db_path = self.ui_to_db_map.get(ui_path)
        if not db_path:
            logger.warning(f"No DB mapping for UI setting: {ui_path}")
            return False
            
        table, column = db_path.split('.')
        try:
            # Update DuckDB
            self.session.execute(f"""
                UPDATE {table} 
                SET {column} = ?
                WHERE id = (SELECT MAX(id) FROM {table})
            """, (new_value,))
            self.session.commit()
            
            logger.info(f"Updated setting {ui_path} to {new_value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update setting {ui_path}: {str(e)}")
            return False
    
    def export_to_yaml(self, file_path: str) -> bool:
        """Export current settings from DuckDB to YAML"""
        try:
            settings = {}
            # Query each settings table
            for ui_path, db_path in self.ui_to_db_map.items():
                table, column = db_path.split('.')
                result = self.session.execute(f"""
                    SELECT {column} 
                    FROM {table} 
                    WHERE id = (SELECT MAX(id) FROM {table})
                """).fetchone()
                
                if result:
                    # Convert flat DB path to nested YAML structure
                    current = settings
                    parts = ui_path.split('.')
                    for part in parts[:-1]:
                        current = current.setdefault(part, {})
                    current[parts[-1]] = result[0]
            
            # Write to YAML
            with open(file_path, 'w') as f:
                yaml.dump(settings, f, default_flow_style=False)
                
            logger.info(f"Exported settings to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export settings: {str(e)}")
            return False
    
    def import_from_yaml(self, file_path: str) -> bool:
        """Import settings from YAML to DuckDB"""
        try:
            with open(file_path, 'r') as f:
                settings = yaml.safe_load(f)
            
            success = True
            # Flatten YAML structure to match DB
            for ui_path, db_path in self.ui_to_db_map.items():
                value = settings
                for part in ui_path.split('.'):
                    if part not in value:
                        break
                    value = value[part]
                else:
                    # Found the value, update DB
                    if not self.update_setting(ui_path, value):
                        success = False
            
            if success:
                logger.info(f"Imported settings from {file_path}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to import settings: {str(e)}")
            return False
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings as a dictionary"""
        settings = {}
        for ui_path in self.ui_to_db_map:
            value = self.get_setting(ui_path)
            if value is not None:
                # Convert flat path to nested structure
                current = settings
                parts = ui_path.split('.')
                for part in parts[:-1]:
                    current = current.setdefault(part, {})
                current[parts[-1]] = value
        return settings 