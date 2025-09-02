import streamlit as st
import sys
import os
import shutil
import subprocess
from pathlib import Path
import yaml
import asyncio

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from goldflipper.config.config import config
from goldflipper.tools.get_alpaca_info import test_alpaca_connection

# New imports for DB init/seed
from goldflipper.database.connection import (
	config as dbconfig,
	init_db,
	get_db_connection,
	backup_database,
)
from sqlalchemy import text
from goldflipper.database.models import WEMStock

# Page configuration
st.set_page_config(
    page_title="Goldflipper Setup",
    page_icon="⚙️",
    layout="wide"
)


def create_shortcut():
    """Create desktop shortcut for Goldflipper"""
    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        package_root = project_root
        icon_path = os.path.join(package_root, "goldflipper.ico")
        
        shortcut_path = os.path.join(desktop, "Goldflipper.lnk")
        target_path = os.path.join(package_root, "launch_goldflipper.bat")
        
        # Create shortcut using PowerShell
        ps_command = f'''
        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
        $Shortcut.TargetPath = "{target_path}"
        $Shortcut.WorkingDirectory = "{package_root}"
        $Shortcut.Description = "Launch Goldflipper Trading Application"
        $Shortcut.IconLocation = "{icon_path}"
        $Shortcut.Save()
        '''
        
        result = subprocess.run(['powershell', '-Command', ps_command], 
                             capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Failed to create shortcut: {result.stderr}")
            
        return True
    except Exception as e:
        st.error(f"Error creating shortcut: {str(e)}")
        return False


def save_settings(settings):
    """Save settings to YAML file"""
    try:
        config_dir = project_root / 'config'
        config_dir.mkdir(exist_ok=True)
        settings_file = config_dir / 'settings.yaml'
        
        with open(settings_file, 'w') as f:
            yaml.dump(settings, f, default_flow_style=False)
        return True
    except Exception as e:
        st.error(f"Error saving settings: {str(e)}")
        return False


# Helpers for DB seeding/overwrite

def _seed_defaults_if_empty():
    """Seed baseline defaults if DB tables are empty (idempotent)."""
    try:
        defaults_file = None
        for p in [
            project_root / 'web' / 'wem_template' / 'default_tickers.txt',
            Path(sys._MEIPASS) / 'web' / 'wem_template' / 'default_tickers.txt' if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS') else None,
        ]:
            if p and p.exists():
                defaults_file = p
                break
        with get_db_connection() as session:
            # WEM stocks
            try:
                count = session.execute(text("SELECT COUNT(*) FROM wem_stocks")).scalar()  # type: ignore
                if not count:
                    if defaults_file is not None:
                        symbols = [s.strip().upper() for s in defaults_file.read_text(encoding='utf-8').splitlines() if s.strip()]
                        for sym in symbols:
                            session.add(WEMStock(symbol=sym, is_default=True))
                        st.success(f"Seeded {len(symbols)} default WEM tickers")
            except Exception as e:
                st.warning(f"WEM seed skipped: {e}")

            # user_settings baseline
            try:
                scount = session.execute(text("SELECT COUNT(*) FROM user_settings")).scalar()  # type: ignore
                if not scount:
                    # Add just a minimal baseline; UI will let user customize
                    session.execute(text("""
                        INSERT INTO user_settings (category, key, value)
                        VALUES
                        ('market_data_providers','yfinance.enabled','true')
                        ON CONFLICT (category, key) DO NOTHING
                    """))
            except Exception as e:
                st.warning(f"Settings seed skipped: {e}")
    except Exception as e:
        st.warning(f"Seeding skipped: {e}")


def _find_bundled_seed_db() -> Path | None:
    candidates = [
        project_root / 'web' / 'data' / 'db' / 'goldflipper.db',
    ]
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base = Path(sys._MEIPASS)
        candidates.extend([
            base / 'web' / 'data' / 'db' / 'goldflipper.db',
            base / 'goldflipper' / 'data' / 'db' / 'goldflipper.db',
        ])
    for p in candidates:
        if p.exists():
            return p
    return None


async def validate_alpaca_credentials(api_key, api_secret, paper_trading):
    """Validate Alpaca API credentials"""
    try:
        # Temporarily set the credentials in the config
        config.set('alpaca', 'api_key', api_key)
        config.set('alpaca', 'api_secret', api_secret)
        config.set('alpaca', 'paper_trading', paper_trading)
        
        # Test the connection
        connection_status, message = await test_alpaca_connection()
        return connection_status, message
    except Exception as e:
        return False, str(e)


def main():
    st.title("Goldflipper Setup")
    st.markdown("""
    Welcome to the Goldflipper setup wizard. This will help you configure your trading accounts and basic settings.
    """)

    # Initialize session state for multi-step setup
    if 'setup_step' not in st.session_state:
        st.session_state.setup_step = 0
    if 'settings' not in st.session_state:
        st.session_state.settings = {
            'alpaca': {
                'accounts': {},
                'active_account': None
            }
        }

    # Step 0: Database Setup / Import vs Overwrite
    if st.session_state.setup_step == 0:
        st.subheader("Step 0: Database Setup")
        db_path = Path(dbconfig.db_path)
        st.write(f"Database location: `{db_path}`")
        exists = db_path.exists()
        if exists:
            st.info("An existing database was detected.")
            choice = st.radio("Choose an action", ["Use existing database (recommended)", "Overwrite with defaults"], index=0)
            if choice == "Use existing database (recommended)":
                if st.button("Continue"):
                    try:
                        init_db()
                        _seed_defaults_if_empty()
                        st.session_state.setup_step = 1
                        st.rerun()
                    except Exception as e:
                        st.error(f"Initialization failed: {e}")
            else:
                st.warning("Overwrite will delete your current database file after creating a backup.")
                confirm = st.checkbox("I understand and want to overwrite with defaults")
                if st.button("Overwrite and Continue", disabled=not confirm):
                    try:
                        # Backup then overwrite
                        try:
                            backup_path = backup_database()
                            st.success(f"Backup created at: {backup_path}")
                        except Exception as be:
                            st.warning(f"Backup failed or skipped: {be}")
                        seed_src = _find_bundled_seed_db()
                        db_path.parent.mkdir(parents=True, exist_ok=True)
                        if db_path.exists():
                            db_path.unlink(missing_ok=True)
                        if seed_src and seed_src.exists():
                            shutil.copy2(seed_src, db_path)
                        init_db()
                        _seed_defaults_if_empty()
                        st.session_state.setup_step = 1
                        st.rerun()
                    except Exception as e:
                        st.error(f"Overwrite failed: {e}")
        else:
            st.info("No database found. We'll initialize and seed defaults.")
            if st.button("Initialize and Continue"):
                try:
                    init_db()
                    _seed_defaults_if_empty()
                    st.session_state.setup_step = 1
                    st.rerun()
                except Exception as e:
                    st.error(f"Initialization failed: {e}")

    # Step 1: Desktop Shortcut
    elif st.session_state.setup_step == 1:
        st.subheader("Step 1: Create Desktop Shortcut")
        st.markdown("""
        Would you like to create a desktop shortcut for easy access to Goldflipper?
        """)
        
        if st.button("Create Desktop Shortcut"):
            if create_shortcut():
                st.success("Desktop shortcut created successfully!")
            st.session_state.setup_step = 2
            st.rerun()
        
        if st.button("Skip and Continue"):
            st.session_state.setup_step = 2
            st.rerun()

    # Step 2: Settings Import
    elif st.session_state.setup_step == 2:
        st.subheader("Step 2: Import Existing Settings")
        st.markdown("""
        Do you have an existing settings.yaml file that you'd like to import?
        """)
        
        uploaded_file = st.file_uploader("Upload settings.yaml", type=['yaml'])
        if uploaded_file is not None:
            try:
                settings_content = uploaded_file.getvalue().decode()
                settings = yaml.safe_load(settings_content)
                st.session_state.settings = settings
                st.success("Settings imported successfully!")
            except Exception as e:
                st.error(f"Error importing settings: {str(e)}")
        
        if st.button("Continue"):
            st.session_state.setup_step = 3
            st.rerun()

    # Step 3: Alpaca API Configuration
    elif st.session_state.setup_step == 3:
        st.subheader("Step 3: Alpaca API Configuration")
        
        api_key = st.text_input("Alpaca API Key", type="password")
        api_secret = st.text_input("Alpaca API Secret", type="password")
        paper_trading = st.checkbox("Use Paper Trading", value=True)
        
        if st.button("Validate and Next"):
            if api_key and api_secret:
                with st.spinner("Validating API credentials..."):
                    connection_status, message = asyncio.run(validate_alpaca_credentials(api_key, api_secret, paper_trading))
                    
                    if connection_status:
                        st.success("API credentials validated successfully!")
                        st.session_state.settings['alpaca']['api_key'] = api_key
                        st.session_state.settings['alpaca']['api_secret'] = api_secret
                        st.session_state.settings['alpaca']['paper_trading'] = paper_trading
                        st.session_state.setup_step = 4
                        st.rerun()
                    else:
                        st.error(f"API validation failed: {message}")
            else:
                st.error("Please enter both API key and secret")

    # Step 4: Account Configuration
    elif st.session_state.setup_step == 4:
        st.subheader("Step 4: Account Configuration")
        
        account_name = st.text_input("Account Name (e.g., 'main_account')")
        account_nickname = st.text_input("Display Name (e.g., 'Main Trading Account')")
        
        if st.button("Add Account"):
            if account_name and account_nickname:
                st.session_state.settings['alpaca']['accounts'][account_name] = {
                    'nickname': account_nickname,
                    'enabled': True,
                    'api_key': st.session_state.settings['alpaca']['api_key'],
                    'api_secret': st.session_state.settings['alpaca']['api_secret'],
                    'paper_trading': st.session_state.settings['alpaca']['paper_trading']
                }
                st.session_state.settings['alpaca']['active_account'] = account_name
                st.success(f"Added account: {account_nickname}")
                st.rerun()
            else:
                st.error("Please enter both account name and display name")
        
        # Display added accounts
        if st.session_state.settings['alpaca']['accounts']:
            st.markdown("### Added Accounts")
            for name, info in st.session_state.settings['alpaca']['accounts'].items():
                st.markdown(f"- {info['nickname']} ({name})")
            
            if st.button("Complete Setup"):
                if save_settings(st.session_state.settings):
                    st.success("Setup completed successfully!")
                    st.balloons()
                    st.markdown("""
                    ### Next Steps
                    1. Return to the main page
                    2. Select your trading account
                    3. Start trading!
                    """)
                else:
                    st.error("Failed to save settings. Please try again.")


if __name__ == "__main__":
    main() 