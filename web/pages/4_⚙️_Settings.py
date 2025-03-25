import streamlit as st
import sys
import os
from pathlib import Path
import yaml
import logging
from datetime import datetime

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

from goldflipper.config.config import config
from goldflipper.database.connection import get_db_connection
from web.utils.settings_manager import SettingsManager

# Page configuration
st.set_page_config(
    page_title="GoldFlipper Settings",
    page_icon="⚙️",
    layout="wide"
)

# Add logging configuration
logger = logging.getLogger(__name__)

def load_settings():
    """Load current settings from YAML file"""
    try:
        settings_file = project_root / 'goldflipper' / 'config' / 'settings.yaml'
        if not settings_file.exists():
            return None
        with open(settings_file, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        st.error(f"Error loading settings: {str(e)}")
        return None

def save_settings(new_settings):
    """Save settings to YAML file while preserving structure and comments"""
    try:
        config_dir = project_root / 'goldflipper' / 'config'
        config_dir.mkdir(exist_ok=True)
        settings_file = config_dir / 'settings.yaml'
        
        # Load existing settings with structure
        current_settings = {}
        if settings_file.exists():
            with open(settings_file, 'r') as f:
                current_settings = yaml.safe_load(f)
        
        def update_nested_dict(current, new):
            """Update nested dictionary while preserving structure"""
            for k, v in new.items():
                if isinstance(v, dict) and k in current and isinstance(current[k], dict):
                    # Recursively update nested dictionaries
                    update_nested_dict(current[k], v)
                else:
                    # Only update if value actually changed
                    if k not in current or current[k] != v:
                        logger.debug(f"Updating setting: {k} = {v}")
                        current[k] = v
        
        # Update only changed values while preserving structure
        update_nested_dict(current_settings, new_settings)
        
        # Read existing file to preserve comments and format
        existing_content = ""
        if settings_file.exists():
            with open(settings_file, 'r') as f:
                existing_content = f.read()
        
        # Write back with preserved structure
        with open(settings_file, 'w') as f:
            if existing_content and '# ===' in existing_content:
                # If file exists and has comments, preserve the format
                yaml_content = yaml.dump(current_settings, default_flow_style=False)
                # Extract header comments if they exist
                header = existing_content[:existing_content.find('---')] if '---' in existing_content else ""
                f.write(header + yaml_content)
            else:
                # New file or no special formatting to preserve
                yaml.dump(current_settings, f, default_flow_style=False)
        
        logger.info("Settings saved successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error saving settings: {str(e)}", exc_info=True)
        st.error(f"Error saving settings: {str(e)}")
        return False

def render_alpaca_account_settings(account_key, account_data):
    """Render settings for a specific Alpaca account"""
    with st.expander(f"Account: {account_data.get('nickname', account_key)}", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            enabled = st.checkbox("Enable Account", value=account_data.get('enabled', False), key=f"alpaca_{account_key}_enabled")
            nickname = st.text_input("Nickname", value=account_data.get('nickname', ''), key=f"alpaca_{account_key}_nickname")
            api_key = st.text_input("API Key", value=account_data.get('api_key', ''), key=f"alpaca_{account_key}_api_key")
        with col2:
            secret_key = st.text_input("Secret Key", value=account_data.get('secret_key', ''), type="password", key=f"alpaca_{account_key}_secret_key")
            base_url = st.text_input("Base URL", value=account_data.get('base_url', ''), key=f"alpaca_{account_key}_base_url")
        
        return {
            'enabled': enabled,
            'nickname': nickname,
            'api_key': api_key,
            'secret_key': secret_key,
            'base_url': base_url
        }

def render_market_data_provider_settings(provider_key, provider_data):
    """Render settings for a specific market data provider"""
    st.subheader(f"Provider: {provider_key.title()}")
    enabled = st.checkbox("Enable Provider", value=provider_data.get('enabled', False), key=f"provider_{provider_key}_enabled")
    
    if provider_key == 'marketdataapp':
        api_key = st.text_input("API Key", value=provider_data.get('api_key', ''), key=f"provider_{provider_key}_api_key")
    elif provider_key == 'alpaca':
        use_websocket = st.checkbox("Use WebSocket", value=provider_data.get('use_websocket', False), key=f"provider_{provider_key}_websocket")
        websocket_symbols = st.text_area("WebSocket Symbols", value="\n".join(provider_data.get('websocket_symbols', [])), key=f"provider_{provider_key}_symbols")
    
    return {
        'enabled': enabled,
        'api_key': api_key if provider_key == 'marketdataapp' else provider_data.get('api_key', ''),
        'use_websocket': use_websocket if provider_key == 'alpaca' else provider_data.get('use_websocket', False),
        'websocket_symbols': websocket_symbols.split('\n') if provider_key == 'alpaca' else provider_data.get('websocket_symbols', [])
    }

def direct_import(session, yaml_file_path):
    """Import settings from YAML directly to database without using SettingsManager."""
    try:
        # Import text function for SQL
        from sqlalchemy import text
        
        # Load the YAML file
        logger.info(f"Direct import: Loading settings from {yaml_file_path}")
        with open(yaml_file_path, 'r') as f:
            yaml_settings = yaml.safe_load(f)
        
        if not yaml_settings:
            logger.error("YAML file is empty or invalid")
            return False, None
        
        logger.info(f"Direct import: Loaded YAML with {len(yaml_settings)} top-level keys")
        logger.info(f"Top-level keys: {list(yaml_settings.keys())}")
        
        # Check if user_settings table exists
        try:
            # Simple check with basic SQL - doesn't rely on information schema
            result = session.execute(text("SELECT 1 FROM user_settings LIMIT 1"))
            result.fetchall()  # Just to consume the result
            logger.info("User settings table exists")
        except Exception as e:
            # Try creating the table if it doesn't exist
            logger.warning(f"Error checking user_settings table: {str(e)}")
            try:
                logger.info("Attempting to create user_settings table...")
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
                session.commit()
                logger.info("Created user_settings table")
            except Exception as create_error:
                logger.error(f"Failed to create user_settings table: {str(create_error)}")
                st.error("Could not find or create the user_settings table. Please run the migration first.")
                return False, None
        
        # Flatten settings manually
        flattened = {}
        def _flatten(settings, prefix=''):
            for key, value in settings.items():
                # Skip comment keys
                if str(key).startswith('#'):
                    continue
                
                # Skip None values
                if value is None:
                    continue
                
                full_key = f"{prefix}.{key}" if prefix else key
                
                if isinstance(value, dict):
                    _flatten(value, full_key)
                else:
                    # Convert lists and other complex objects to JSON
                    if isinstance(value, (list, dict)):
                        import json
                        value = json.dumps(value)
                    elif not isinstance(value, (str, int, float, bool)):
                        value = str(value)
                    
                    # Split into category and key
                    if '.' not in full_key:
                        category = full_key
                        setting_key = ''
                    else:
                        parts = full_key.split('.')
                        category = parts[0]
                        setting_key = '.'.join(parts[1:])
                    
                    flattened[(category, setting_key)] = value
        
        _flatten(yaml_settings)
        logger.info(f"Direct import: Flattened {len(flattened)} settings")
        
        # Show sample of flattened settings
        sample_keys = list(flattened.keys())[:5]
        logger.info(f"Sample flattened keys: {sample_keys}")
        
        # Insert settings directly to database - use simple SQL for DuckDB compatibility
        import uuid
        from datetime import datetime
        import json
        
        # Get a new session to avoid context manager issues
        success_count = 0
        error_count = 0
        
        # Use one-by-one inserts with simple SQL
        for (category, key), value in flattened.items():
            try:
                # First delete any existing setting
                session.execute(
                    text("DELETE FROM user_settings WHERE category = :category AND key = :key"),
                    {"category": category, "key": key}
                )
                
                # Then insert the new setting
                session.execute(
                    text("INSERT INTO user_settings (id, category, key, value, last_modified) VALUES (:id, :category, :key, :value, :last_modified)"),
                    {
                        "id": str(uuid.uuid4()),
                        "category": category,
                        "key": key,
                        "value": value,
                        "last_modified": datetime.utcnow().isoformat()
                    }
                )
                success_count += 1
                if success_count % 10 == 0:
                    logger.info(f"Imported {success_count} settings so far...")
            except Exception as e:
                logger.error(f"Error importing setting {category}.{key}: {str(e)}")
                error_count += 1
        
        # Commit transaction if any settings were successful
        if success_count > 0:
            session.commit()
            logger.info(f"Direct import: Inserted {success_count} settings with {error_count} errors")
        else:
            logger.error("No settings were successfully inserted")
            return False, None
        
        # Reload settings to return
        try:
            logger.info("Reloading settings from database")
            result = session.execute(text("SELECT category, key, value FROM user_settings")).fetchall()
            logger.info(f"Retrieved {len(result)} settings from database")
            
            settings = {}
            for row in result:
                cat, key, value = row
                if cat not in settings:
                    settings[cat] = {}
                
                # Handle nested keys
                current = settings[cat]
                if key:  # Skip empty keys
                    parts = key.split('.')
                    for part in parts[:-1]:
                        current = current.setdefault(part, {})
                    current[parts[-1]] = value
            
            return True, settings
        except Exception as e:
            logger.error(f"Error reloading settings: {str(e)}", exc_info=True)
            return False, None
    
    except Exception as e:
        logger.error(f"Error in direct import: {str(e)}", exc_info=True)
        st.error(f"Error in direct import: {str(e)}")
        return False, None

def main():
    st.title("GoldFlipper Settings")
    
    try:
        # First try to read settings from YAML file
        logger.info("Reading settings directly from YAML file...")
        
        # Try finding the settings file at different possible paths
        possible_paths = [
            project_root / 'goldflipper' / 'config' / 'settings.yaml',
            project_root / 'goldflipper' / 'goldflipper' / 'config' / 'settings.yaml',
            Path.cwd() / 'goldflipper' / 'goldflipper' / 'config' / 'settings.yaml',
            Path.cwd() / 'goldflipper' / 'config' / 'settings.yaml'
        ]
        
        found_path = None
        for path in possible_paths:
            if path.exists():
                found_path = path
                logger.info(f"Found settings.yaml at: {path}")
                break
            logger.warning(f"settings.yaml not found at: {path}")
        
        settings = {}
        
        if found_path:
            try:
                logger.info(f"Reading YAML file: {found_path}")
                with open(found_path, 'r') as f:
                    yaml_settings = yaml.safe_load(f)
                    if yaml_settings:
                        logger.info(f"Successfully loaded settings from YAML with {len(yaml_settings)} top-level keys")
                        settings = yaml_settings
                        st.success(f"Successfully loaded settings from: {found_path}")
                    else:
                        logger.error("YAML file is empty or invalid")
                        st.error("Settings file is empty or invalid. Using default settings.")
                        settings = {}
            except Exception as e:
                logger.error(f"Error reading settings from YAML: {str(e)}")
                st.error(f"Error reading settings: {str(e)}")
                settings = {}
        else:
            st.error("Could not find settings.yaml in any expected location.")
            settings = {}
        
        # Now try to connect to database (if we need it later)
        try:
            logger.info("Initializing database connection...")
            db = get_db_connection()
            
            # Import and initialize settings manager
            from goldflipper.database.migrations.add_settings_schema import upgrade
            
            # Initialize settings manager
            settings_manager = SettingsManager(db)
            
            # Check if we should try to run the migration
            if st.sidebar.button("Initialize Database"):
                with st.spinner("Creating database schema..."):
                    try:
                        # Create tables manually first
                        from sqlalchemy import text
                        logger.info("Creating tables manually...")
                        
                        # Create settings_schema table
                        db.execute(text("""
                            CREATE TABLE IF NOT EXISTS settings_schema (
                                id VARCHAR PRIMARY KEY,
                                category VARCHAR UNIQUE NOT NULL,
                                schema VARCHAR,
                                ui_schema VARCHAR,
                                last_modified TIMESTAMP
                            )
                        """))
                        
                        # Create user_settings table
                        db.execute(text("""
                            CREATE TABLE IF NOT EXISTS user_settings (
                                id VARCHAR PRIMARY KEY,
                                category VARCHAR NOT NULL,
                                key VARCHAR,
                                value VARCHAR,
                                last_modified TIMESTAMP,
                                UNIQUE(category, key)
                            )
                        """))
                        db.commit()
                        
                        # Run migration
                        logger.info("Running migration...")
                        upgrade()
                        
                        # Check if database has settings
                        db_settings = settings_manager.get_settings()
                        if not db_settings and settings:
                            # Import from YAML
                            logger.info("Importing settings from YAML to database...")
                            if settings_manager.update_settings(settings):
                                st.success("Successfully imported settings to database!")
                            else:
                                st.error("Failed to import settings to database.")
                        
                        st.success("Database initialized successfully!")
                    except Exception as e:
                        logger.error(f"Error initializing database: {str(e)}")
                        st.error(f"Error initializing database: {str(e)}")
            
            # Add button to import settings from YAML to database
            if st.sidebar.button("Import Settings to Database"):
                if settings:
                    with st.spinner("Importing settings..."):
                        if settings_manager.update_settings(settings):
                            st.success("Successfully imported settings to database!")
                        else:
                            st.error("Failed to import settings to database.")
                else:
                    st.error("No settings to import.")
        except Exception as e:
            logger.error(f"Error connecting to database: {str(e)}")
            st.sidebar.error(f"Database connection error: {str(e)}")
            # Continue with YAML settings only
        
        # Create tabs for different setting categories
        st.write("## Settings")
        tabs = st.tabs(["Logging", "Market Data", "Trading", "System"])

        # Logging Settings Tab
        with tabs[0]:
            st.write("### Logging Settings")
            
            # Global Settings
            st.write("#### Global Settings")
            col1, col2 = st.columns(2)
            
            with col1:
                # Log Level
                current_level = settings.get('logging', {}).get('global', {}).get('level', 'INFO')
                new_level = st.selectbox(
                    "Log Level",
                    ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                    index=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].index(current_level)
                )
                
                # Log Format
                current_format = settings.get('logging', {}).get('global', {}).get('format', '%(asctime)s - %(levelname)s - %(message)s')
                new_format = st.text_input("Log Format", value=current_format)
            
            with col2:
                # File Rotation
                current_rotation = settings.get('logging', {}).get('global', {}).get('file_rotation', True)
                new_rotation = st.checkbox("Enable File Rotation", value=current_rotation)
                
                # Console Output
                current_console = settings.get('logging', {}).get('global', {}).get('console_output', True)
                new_console = st.checkbox("Enable Console Output", value=current_console)
            
            # Module Settings
            st.write("#### Module Settings")
            modules = ['wem', 'market_data', 'trading', 'database', 'plays']
            for module in modules:
                with st.expander(f"{module.replace('_', ' ').title()} Module"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Module Log Level
                        current_level = settings.get('logging', {}).get('modules', {}).get(module, {}).get('level', 'INHERIT')
                        new_level = st.selectbox(
                            f"{module} Log Level",
                            ['INHERIT', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                            index=['INHERIT', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].index(current_level),
                            key=f"{module}_level"
                        )
                    
                    with col2:
                        # Module Log Format
                        current_format = settings.get('logging', {}).get('modules', {}).get(module, {}).get('format', '')
                        new_format = st.text_input(f"{module} Log Format", value=current_format, key=f"{module}_format")
                        
                        # Module Log File
                        current_file = settings.get('logging', {}).get('modules', {}).get(module, {}).get('file', '')
                        new_file = st.text_input(f"{module} Log File", value=current_file, key=f"{module}_file")

        # Market Data Tab
        with tabs[1]:
            st.write("### Market Data Settings")
            st.info("Market Data settings coming soon...")

        # Trading Tab
        with tabs[2]:
            st.write("### Trading Settings")
            st.info("Trading settings coming soon...")

        # System Tab
        with tabs[3]:
            st.write("### System Settings")
            st.info("System settings coming soon...")

        # Save button at the bottom
        if st.button("Save Settings"):
            # Generate updated settings
            updated_settings = {
                'logging': {
                    'global': {
                        'level': new_level,
                        'format': new_format,
                        'file_rotation': new_rotation,
                        'console_output': new_console
                    },
                    'modules': {}
                }
            }
            
            # Update module settings
            for module in modules:
                module_level = st.session_state.get(f"{module}_level")
                module_format = st.session_state.get(f"{module}_format")
                module_file = st.session_state.get(f"{module}_file")
                
                if module_level or module_format or module_file:
                    updated_settings['logging']['modules'][module] = {}
                    
                    if module_level:
                        updated_settings['logging']['modules'][module]['level'] = module_level
                    if module_format:
                        updated_settings['logging']['modules'][module]['format'] = module_format
                    if module_file:
                        updated_settings['logging']['modules'][module]['file'] = module_file
            
            # Save to YAML
            if save_settings(updated_settings):
                st.success("Settings saved successfully!")
                st.balloons()
            else:
                st.error("Failed to save settings. Please try again.")

    except Exception as e:
        st.error(f"Error initializing settings: {str(e)}")
        logger.error(f"Error in main function: {str(e)}", exc_info=True)
        return

if __name__ == "__main__":
    main() 