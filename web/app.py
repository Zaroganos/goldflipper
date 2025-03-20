import streamlit as st
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from goldflipper.config.config import config

# Page configuration
st.set_page_config(
    page_title="GoldFlipper",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Redirect to Home page
st.switch_page("pages/0_🏠_Home.py")

def get_accounts():
    """Get configured accounts with error handling"""
    try:
        accounts = config.get('alpaca', 'accounts')
        if not accounts:
            st.error("No trading accounts configured. Please run the setup wizard first.")
            return None
        return accounts
    except Exception as e:
        st.error(f"Error loading accounts: {str(e)}")
        return None

def main():
    # Sidebar
    with st.sidebar:
        # Logo
        logo_path = project_root / 'web' / 'assets' / 'logo.png'
        if logo_path.exists():
            st.image(str(logo_path), width=200)
        else:
            st.title("GoldFlipper")
        
        # Navigation
        st.markdown("### Navigation")
        page = st.radio(
            "Select a page",
            ["Dashboard", "Trading", "Analysis", "Settings"],
            index=0
        )
        
        # Account Selection
        st.markdown("### Trading Account")
        accounts = get_accounts()
        if accounts:
            account_names = [acc.get('nickname', name) for name, acc in accounts.items()]
            selected_account = st.selectbox(
                "Select Account",
                options=account_names,
                index=0
            )
        
        # About Section
        st.markdown("---")
        st.markdown("### About")
        st.markdown("GoldFlipper v1.0.0")
        st.markdown("A professional trading automation platform")
    
    # Main Content
    st.title("Welcome to GoldFlipper")
    
    if page == "Dashboard":
        st.write("Dashboard content coming soon...")
    elif page == "Trading":
        st.write("Trading interface coming soon...")
    elif page == "Analysis":
        st.write("Analysis tools coming soon...")
    elif page == "Settings":
        st.write("Settings page coming soon...")

if __name__ == "__main__":
    main() 