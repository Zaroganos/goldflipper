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
    
    Please fill in the information below to get started.
    """)
    
    # Initialize session state for multi-step setup
    if 'setup_step' not in st.session_state:
        st.session_state.setup_step = 1
    if 'settings' not in st.session_state:
        st.session_state.settings = {
            'alpaca': {
                'accounts': {},
                'active_account': None
            }
        }
    
    # Step 1: Desktop Shortcut
    if st.session_state.setup_step == 1:
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