import streamlit as st
import sys
import os
from pathlib import Path
import yaml

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from goldflipper.config.config import config

# Page configuration
st.set_page_config(
    page_title="GoldFlipper Settings",
    page_icon="⚙️",
    layout="wide"
)

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

def save_settings(settings):
    """Save settings to YAML file"""
    try:
        config_dir = project_root / 'goldflipper' / 'config'
        config_dir.mkdir(exist_ok=True)
        settings_file = config_dir / 'settings.yaml'
        
        with open(settings_file, 'w') as f:
            yaml.dump(settings, f, default_flow_style=False)
        return True
    except Exception as e:
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

def main():
    st.title("GoldFlipper Settings")
    
    # Load current settings
    settings = load_settings()
    if not settings:
        st.error("Could not load settings. Please run the setup wizard first.")
        return
    
    # Create tabs for different setting categories
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "Trading Accounts",
        "Trading Parameters",
        "Market Data",
        "Chart Settings",
        "System Settings",
        "File Operations",
        "Advanced",
        "WEM Settings"
    ])
    
    # Trading Accounts Tab
    with tab1:
        st.subheader("Trading Accounts")
        
        # Display current accounts
        if 'alpaca' in settings and 'accounts' in settings['alpaca']:
            for name, account in settings['alpaca']['accounts'].items():
                render_alpaca_account_settings(name, account)
        
        # Add new account
        if st.button("Add New Account"):
            new_account = {
                'nickname': st.text_input("Display Name", key="new_account_nickname"),
                'enabled': True,
                'api_key': st.text_input("API Key", type="password", key="new_account_api_key"),
                'secret_key': st.text_input("Secret Key", type="password", key="new_account_secret_key"),
                'base_url': st.text_input("Base URL", key="new_account_base_url"),
                'paper_trading': st.checkbox("Paper Trading", True, key="new_account_paper_trading")
            }
            if new_account['nickname'] and new_account['api_key'] and new_account['secret_key']:
                account_name = new_account['nickname'].lower().replace(' ', '_')
                settings['alpaca']['accounts'][account_name] = new_account
                st.success(f"Added account: {new_account['nickname']}")
                st.rerun()
    
    # Trading Parameters Tab
    with tab2:
        st.subheader("Trading Parameters")
        
        # Options Swings Settings
        if 'options_swings' not in settings:
            settings['options_swings'] = {}
        
        with st.expander("Options Swings Settings"):
            settings['options_swings']['enabled'] = st.checkbox("Enable Options Swings", 
                                                             settings['options_swings'].get('enabled', True))
            
            if settings['options_swings']['enabled']:
                col1, col2 = st.columns(2)
                with col1:
                    settings['options_swings']['entry_order_types'] = st.multiselect(
                        "Entry Order Types",
                        options=['market', 'limit'],
                        default=settings['options_swings'].get('entry_order_types', ['market', 'limit']),
                        key="options_swings_entry_order_types"
                    )
                    settings['options_swings']['TP-SL_types'] = st.multiselect(
                        "Take Profit/Stop Loss Types",
                        options=['STOCK_PRICE', 'PREMIUM_PCT', 'STOCK_PRICE_PCT'],
                        default=settings['options_swings'].get('TP-SL_types', ['STOCK_PRICE', 'PREMIUM_PCT', 'STOCK_PRICE_PCT']),
                        key="options_swings_tp_sl_types"
                    )
                with col2:
                    settings['options_swings']['expiration_days'] = st.number_input(
                        "Default Expiration (days)",
                        min_value=1,
                        max_value=365,
                        value=settings['options_swings'].get('expiration_days', 14)
                    )
                    settings['options_swings']['entry_buffer'] = st.number_input(
                        "Entry Price Buffer",
                        min_value=0.0,
                        max_value=1.0,
                        step=0.01,
                        value=settings['options_swings'].get('entry_buffer', 0.05)
                    )
        
        # Order Settings
        if 'orders' not in settings:
            settings['orders'] = {}
        
        with st.expander("Order Settings"):
            settings['orders']['limit_order'] = {
                'timeout_enabled': st.checkbox("Enable Limit Order Timeout",
                                            settings['orders'].get('limit_order', {}).get('timeout_enabled', False)),
                'max_duration_minutes': st.number_input(
                    "Maximum Duration (minutes)",
                    min_value=1,
                    max_value=60,
                    value=settings['orders'].get('limit_order', {}).get('max_duration_minutes', 5)
                ),
                'check_interval_seconds': st.number_input(
                    "Check Interval (seconds)",
                    min_value=1,
                    max_value=300,
                    value=settings['orders'].get('limit_order', {}).get('check_interval_seconds', 30)
                )
            }
            
            settings['orders']['bid_price_settings'] = {
                'use_bid_price': st.checkbox("Use Bid Price for Orders",
                                          settings['orders'].get('bid_price_settings', {}).get('use_bid_price', True)),
                'entry': st.checkbox("Use Bid Price for Entry",
                                  settings['orders'].get('bid_price_settings', {}).get('entry', True)),
                'take_profit': st.checkbox("Use Bid Price for Take Profit",
                                        settings['orders'].get('bid_price_settings', {}).get('take_profit', True)),
                'stop_loss': st.checkbox("Use Bid Price for Stop Loss",
                                      settings['orders'].get('bid_price_settings', {}).get('stop_loss', True))
            }
    
    # Market Data Tab
    with tab3:
        st.subheader("Market Data Settings")
        
        # Market Hours
        if 'market_hours' not in settings:
            settings['market_hours'] = {}
        
        with st.expander("Market Hours"):
            settings['market_hours']['enabled'] = st.checkbox("Enable Market Hours Validation",
                                                           settings['market_hours'].get('enabled', True))
            
            if settings['market_hours']['enabled']:
                col1, col2 = st.columns(2)
                with col1:
                    settings['market_hours']['regular_hours'] = {
                        'start': st.text_input("Market Open (HH:MM)", 
                                             settings['market_hours'].get('regular_hours', {}).get('start', '09:29')),
                        'end': st.text_input("Market Close (HH:MM)", 
                                           settings['market_hours'].get('regular_hours', {}).get('end', '16:16'))
                    }
                with col2:
                    settings['market_hours']['extended_hours'] = {
                        'enabled': st.checkbox("Enable Extended Hours",
                                             settings['market_hours'].get('extended_hours', {}).get('enabled', False)),
                        'pre_market_start': st.text_input("Pre-market Start (HH:MM)",
                                                        settings['market_hours'].get('extended_hours', {}).get('pre_market_start', '04:00')),
                        'after_market_end': st.text_input("After-market End (HH:MM)",
                                                        settings['market_hours'].get('extended_hours', {}).get('after_market_end', '20:00'))
                    }
        
        # Market Data Providers
        if 'market_data_providers' not in settings:
            settings['market_data_providers'] = {}
        
        with st.expander("Market Data Providers"):
            settings['market_data_providers']['primary_provider'] = st.selectbox(
                "Primary Provider",
                options=["marketdataapp", "alpaca", "yfinance"],
                index=["marketdataapp", "alpaca", "yfinance"].index(
                    settings['market_data_providers'].get('primary_provider', 'marketdataapp')
                )
            )
            
            # MarketDataApp Settings
            if 'providers' not in settings['market_data_providers']:
                settings['market_data_providers']['providers'] = {}
            
            with st.subheader("MarketDataApp Settings"):
                settings['market_data_providers']['providers']['marketdataapp'] = render_market_data_provider_settings('marketdataapp', settings['market_data_providers']['providers'].get('marketdataapp', {}))
            
            # Alpaca Settings
            with st.subheader("Alpaca Settings"):
                settings['market_data_providers']['providers']['alpaca'] = render_market_data_provider_settings('alpaca', settings['market_data_providers']['providers'].get('alpaca', {}))
            
            # Yahoo Finance Settings
            with st.subheader("Yahoo Finance Settings"):
                settings['market_data_providers']['providers']['yfinance'] = {
                    'enabled': st.checkbox("Enable Yahoo Finance",
                                         settings['market_data_providers']['providers'].get('yfinance', {}).get('enabled', True))
                }
    
    # Chart Settings Tab
    with tab4:
        st.subheader("Chart Settings")
        
        # Chart Viewer Settings
        if 'chart_viewer' not in settings:
            settings['chart_viewer'] = {}
        
        with st.expander("Chart Display Settings"):
            settings['chart_viewer']['display'] = {
                'style': st.selectbox(
                    "Chart Style",
                    options=["charles", "classic", "yahoo"],
                    index=["charles", "classic", "yahoo"].index(
                        settings['chart_viewer'].get('display', {}).get('style', 'charles')
                    )
                ),
                'candle_up_color': st.color_picker(
                    "Up Candle Color",
                    settings['chart_viewer'].get('display', {}).get('candle_up_color', '#00FF00')
                ),
                'candle_down_color': st.color_picker(
                    "Down Candle Color",
                    settings['chart_viewer'].get('display', {}).get('candle_down_color', '#FF0000')
                ),
                'background_color': st.color_picker(
                    "Background Color",
                    settings['chart_viewer'].get('display', {}).get('background_color', '#FFFFFF')
                ),
                'grid': st.checkbox("Show Grid",
                                  settings['chart_viewer'].get('display', {}).get('grid', True)),
                'grid_alpha': st.slider(
                    "Grid Opacity",
                    min_value=0.0,
                    max_value=1.0,
                    value=settings['chart_viewer'].get('display', {}).get('grid_alpha', 0.2),
                    step=0.1
                )
            }
        
        # Technical Indicators
        if 'indicators' not in settings:
            settings['indicators'] = {}
        
        with st.expander("Technical Indicators"):
            settings['indicators']['enabled'] = st.checkbox("Enable Technical Indicators",
                                                         settings['indicators'].get('enabled', True))
            
            if settings['indicators']['enabled']:
                # TTM Squeeze
                with st.subheader("TTM Squeeze"):
                    settings['indicators']['ttm_squeeze'] = {
                        'enabled': st.checkbox("Enable TTM Squeeze",
                                             settings['indicators'].get('ttm_squeeze', {}).get('enabled', True)),
                        'period': st.number_input("Period",
                                                min_value=1,
                                                value=settings['indicators'].get('ttm_squeeze', {}).get('period', 20)),
                        'bb_multiplier': st.number_input("Bollinger Bands Multiplier",
                                                       min_value=0.1,
                                                       value=settings['indicators'].get('ttm_squeeze', {}).get('bb_multiplier', 2.0),
                                                       step=0.1),
                        'kc_multiplier': st.number_input("Keltner Channel Multiplier",
                                                       min_value=0.1,
                                                       value=settings['indicators'].get('ttm_squeeze', {}).get('kc_multiplier', 1.5),
                                                       step=0.1)
                    }
                
                # EMA
                with st.subheader("EMA"):
                    settings['indicators']['ema'] = {
                        'enabled': st.checkbox("Enable EMA",
                                             settings['indicators'].get('ema', {}).get('enabled', True)),
                        'periods': st.text_input("Periods (comma-separated)",
                                               ",".join(map(str, settings['indicators'].get('ema', {}).get('periods', [9, 21, 55, 200])))
                    ).split(',')
                }
                
                # MACD
                with st.subheader("MACD"):
                    settings['indicators']['macd'] = {
                        'enabled': st.checkbox("Enable MACD",
                                             settings['indicators'].get('macd', {}).get('enabled', True)),
                        'fast_period': st.number_input("Fast Period",
                                                     min_value=1,
                                                     value=settings['indicators'].get('macd', {}).get('fast_period', 12)),
                        'slow_period': st.number_input("Slow Period",
                                                     min_value=1,
                                                     value=settings['indicators'].get('macd', {}).get('slow_period', 26)),
                        'signal_period': st.number_input("Signal Period",
                                                       min_value=1,
                                                       value=settings['indicators'].get('macd', {}).get('signal_period', 9))
                    }
    
    # System Settings Tab
    with tab5:
        st.subheader("System Settings")
        
        # Console Visibility
        with st.expander("Console Settings"):
            show_console_file = project_root / 'web' / 'show_console.txt'
            show_console = False
            if show_console_file.exists():
                with open(show_console_file, 'r') as f:
                    show_console = f.read().strip() == '1'
            
            new_show_console = st.checkbox(
                "Show Console Window",
                value=show_console,
                help="Toggle the visibility of the Streamlit server console window. Changes take effect after restarting the application."
            )
            
            if new_show_console != show_console:
                with open(show_console_file, 'w') as f:
                    f.write('1' if new_show_console else '0')
                st.info("Console visibility setting saved. Please restart the application for changes to take effect.")
        
        # Logging
        if 'logging' not in settings:
            settings['logging'] = {}
        
        with st.expander("Logging Settings"):
            settings['logging']['level'] = st.selectbox(
                "Logging Level",
                options=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                index=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].index(
                    settings['logging'].get('level', 'INFO')
                )
            )
            settings['logging']['format'] = st.text_input(
                "Log Format",
                settings['logging'].get('format', '%(asctime)s - %(levelname)s - %(message)s')
            )
        
        # Monitoring
        if 'monitoring' not in settings:
            settings['monitoring'] = {}
        
        with st.expander("Monitoring Settings"):
            settings['monitoring']['polling_interval'] = st.number_input(
                "Position Check Interval (seconds)",
                min_value=1,
                max_value=300,
                value=settings['monitoring'].get('polling_interval', 30)
            )
            settings['monitoring']['max_retries'] = st.number_input(
                "Maximum Retry Attempts",
                min_value=1,
                max_value=10,
                value=settings['monitoring'].get('max_retries', 3)
            )
            settings['monitoring']['retry_delay'] = st.number_input(
                "Retry Delay (seconds)",
                min_value=1,
                max_value=60,
                value=settings['monitoring'].get('retry_delay', 2)
            )
    
    # File Operations Tab
    with tab6:
        st.subheader("File Operations")
        
        # File Paths
        if 'file_paths' not in settings:
            settings['file_paths'] = {}
        
        with st.expander("File Paths"):
            for key, value in settings['file_paths'].items():
                settings['file_paths'][key] = st.text_input(
                    key.replace('_', ' ').title(),
                    value,
                    key=f"file_path_{key}"
                )
        
        # CSV Ingestor
        if 'csv_ingestor' not in settings:
            settings['csv_ingestor'] = {}
        
        with st.expander("CSV Ingestor Settings"):
            settings['csv_ingestor']['open_after_creation'] = st.checkbox(
                "Open Files After Creation",
                settings['csv_ingestor'].get('open_after_creation', False)
            )
            settings['csv_ingestor']['default_viewer'] = st.selectbox(
                "Default Viewer",
                options=["code", "explorer", "none"],
                index=["code", "explorer", "none"].index(
                    settings['csv_ingestor'].get('default_viewer', 'code')
                )
            )
            settings['csv_ingestor']['validation'] = {
                'enabled': st.checkbox(
                    "Enable Validation",
                    settings['csv_ingestor'].get('validation', {}).get('enabled', True)
                ),
                'strict_mode': st.checkbox(
                    "Strict Mode",
                    settings['csv_ingestor'].get('validation', {}).get('strict_mode', False)
                )
            }
            settings['csv_ingestor']['backup'] = {
                'keep_originals': st.checkbox(
                    "Keep Original Files",
                    settings['csv_ingestor'].get('backup', {}).get('keep_originals', True)
                ),
                'backup_dir': st.text_input(
                    "Backup Directory",
                    settings['csv_ingestor'].get('backup', {}).get('backup_dir', 'ingestor_backups')
                )
            }
    
    # Advanced Tab
    with tab7:
        st.subheader("Advanced Settings")
        
        # Auto Play Creator
        if 'auto_play_creator' not in settings:
            settings['auto_play_creator'] = {}
        
        with st.expander("Auto Play Creator"):
            settings['auto_play_creator']['enabled'] = st.checkbox(
                "Enable Auto Play Creator",
                settings['auto_play_creator'].get('enabled', True)
            )
            
            if settings['auto_play_creator']['enabled']:
                col1, col2 = st.columns(2)
                with col1:
                    settings['auto_play_creator']['order_types'] = st.multiselect(
                        "Order Types",
                        options=['market', 'limit'],
                        default=settings['auto_play_creator'].get('order_types', ['market', 'limit']),
                        key="auto_play_creator_order_types"
                    )
                    settings['auto_play_creator']['TP-SL_types'] = st.multiselect(
                        "Take Profit/Stop Loss Types",
                        options=['STOCK_PRICE', 'PREMIUM_PCT', 'STOCK_PRICE_PCT'],
                        default=settings['auto_play_creator'].get('TP-SL_types', ['STOCK_PRICE', 'PREMIUM_PCT', 'STOCK_PRICE_PCT']),
                        key="auto_play_creator_tp_sl_types"
                    )
                with col2:
                    settings['auto_play_creator']['expiration_days'] = st.number_input(
                        "Default Expiration (days)",
                        min_value=1,
                        max_value=365,
                        value=settings['auto_play_creator'].get('expiration_days', 7)
                    )
                    settings['auto_play_creator']['entry_buffer'] = st.number_input(
                        "Entry Price Buffer",
                        min_value=0.0,
                        max_value=1.0,
                        step=0.01,
                        value=settings['auto_play_creator'].get('entry_buffer', 0.50)
                    )
                
                settings['auto_play_creator']['test_symbols'] = st.text_area(
                    "Test Symbols (one per line)",
                    "\n".join(settings['auto_play_creator'].get('test_symbols', ['SPY', 'QQQ', 'AAPL', 'TSLA', 'NVDA', 'MSFT', 'GOOGL', 'AMZN', 'BABA', 'GME']))
                ).split('\n')
    
    # WEM Settings Tab
    with tab8:
        st.subheader("Weekly Expected Moves (WEM) Settings")
        
        # Load current WEM settings
        wem_settings = config.get('wem', {})
        
        # Default tracked stocks
        if 'tracked_stocks' not in wem_settings:
            wem_settings['tracked_stocks'] = []
        
        st.markdown("### Default Tracked Stocks")
        new_stock = st.text_input("Add Default Stock Symbol")
        if st.button("Add Default Stock") and new_stock:
            if new_stock.upper() not in wem_settings['tracked_stocks']:
                wem_settings['tracked_stocks'].append(new_stock.upper())
                config.set('wem', wem_settings)
                st.success(f"Added {new_stock.upper()} to default tracked stocks")
                st.rerun()
        
        # Display current default stocks
        if wem_settings['tracked_stocks']:
            st.markdown("#### Current Default Stocks:")
            for stock in wem_settings['tracked_stocks']:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(stock)
                with col2:
                    if st.button("Remove", key=f"remove_default_{stock}"):
                        wem_settings['tracked_stocks'].remove(stock)
                        config.set('wem', wem_settings)
                        st.success(f"Removed {stock} from default tracked stocks")
                        st.rerun()
        
        # Calculation Settings
        st.markdown("### Calculation Settings")
        wem_settings['calculation_method'] = st.selectbox(
            "Default Calculation Method",
            ["standard", "advanced", "custom"],
            index=["standard", "advanced", "custom"].index(
                wem_settings.get('calculation_method', 'standard')
            )
        )
        
        wem_settings['update_frequency'] = st.selectbox(
            "Default Update Frequency",
            ["hourly", "daily", "weekly"],
            index=["hourly", "daily", "weekly"].index(
                wem_settings.get('update_frequency', 'daily')
            )
        )
        
        # Advanced Settings
        with st.expander("Advanced WEM Settings"):
            wem_settings['confidence_threshold'] = st.slider(
                "Confidence Threshold (%)",
                min_value=0,
                max_value=100,
                value=wem_settings.get('confidence_threshold', 70),
                step=5
            )
            
            wem_settings['max_stocks'] = st.number_input(
                "Maximum Number of Tracked Stocks",
                min_value=1,
                max_value=100,
                value=wem_settings.get('max_stocks', 20),
                step=1
            )
            
            wem_settings['auto_update'] = st.checkbox(
                "Enable Automatic Updates",
                value=wem_settings.get('auto_update', True)
            )
        
        # Save WEM settings
        if st.button("Save WEM Settings"):
            config.set('wem', wem_settings)
            st.success("WEM settings saved successfully!")
    
    # Save button at the bottom
    if st.button("Save Settings"):
        if save_settings(settings):
            st.success("Settings saved successfully!")
            st.balloons()
        else:
            st.error("Failed to save settings. Please try again.")

if __name__ == "__main__":
    main() 