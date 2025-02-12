from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Button, Static, Select
from textual.screen import Screen
import subprocess
import sys
import os
import threading
import time
import logging
from pathlib import Path
from goldflipper.config.config import config
import yaml
import win32console
import win32con

def setup_logging(console_mode=False):
    """Configure logging with both file and optional console output"""
    
    # Create logs directory if it doesn't exist
    current_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(current_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Configure logging format
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    log_file = os.path.join(log_dir, 'trading_monitor.log')
    
    # Set up handlers
    handlers = [logging.FileHandler(log_file)]
    if console_mode:
        handlers.append(logging.StreamHandler(sys.stdout))
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=handlers
    )
    
    # Log startup message
    logging.info("Logging initialized for trading monitor")

def is_admin():
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

class AdminChoiceScreen(Screen):
    """Screen for choosing whether to run as admin or not"""
    
    def compose(self) -> ComposeResult:
        yield Container(
            Static("Running in regular user mode.\n\n" +
                  "Would you like to:\n" +
                  "1. Continue in regular mode (recommended for normal use)\n" +
                  "2. Restart as administrator (required for service installation)",
                  id="dialog-message"),
            Container(
                Button("Continue", variant="primary", id="continue_regular"),
                Button("Restart as Admin", variant="warning", id="restart_admin"),
                Button("Cancel", variant="error", id="cancel"),
                classes="dialog-buttons"
            ),
            id="dialog-container"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            package_root = os.path.dirname(current_dir)
            
            if event.button.id == "continue_regular":
                self.app.pop_screen()
                cmd = [
                    'cmd', '/c', 
                    'start', 
                    'GoldFlipper Trading System',
                    '/D', package_root,
                    'cmd', '/k',
                    'python', '-m', 'goldflipper.run', '--mode', 'console'
                ]
                self.app.exit()
                subprocess.run(cmd, check=True)
                
            elif event.button.id == "restart_admin":
                self.app.pop_screen()
                cmd = ['powershell', 'Start-Process', 'python', '-ArgumentList',
                       f'"-m goldflipper.run --mode console"',
                       '-Verb', 'RunAs', '-WorkingDirectory', package_root]
                subprocess.run(cmd)
                self.app.exit()
                
            elif event.button.id == "cancel":
                self.app.pop_screen()
                
        except Exception as e:
            self.notify(f"Error handling button press: {str(e)}", severity="error")

class WelcomeScreen(Screen):
    BINDINGS = [("q", "quit", "Quit")]
    
    def compose(self) -> ComposeResult:
        # Determine the default active account:
        # If the settings.yaml already specifies an active_account, use it;
        # otherwise, use the default_account.
        active_account = config.get('alpaca', 'active_account')
        if not active_account:
            active_account = config.get('alpaca', 'default_account')
        
        yield Header()
        yield Container(
            Horizontal(
                Static(" Welcome to Goldflipper ", id="welcome"),
                Select(
                    # Build the options list from all enabled accounts.
                    [(acc.get('nickname', name.replace('_', ' ').title()), name) 
                     for name, acc in config.get('alpaca', 'accounts').items() 
                     if acc.get('enabled', False)],
                    prompt="Select Trading Account",
                    id="account_selector",
                    value=active_account  # Set the preselected account here.
                ),
                id="header_container"
            ),
            Horizontal(
                Container(
                    Button("Create New Play", variant="primary", id="create_play"),
                    Button("Fetch Option Data", variant="primary", id="option_data_fetcher"),
                    Button("Launch Trading System", variant="success", id="start_monitor"),
                    Button("Auto Play Creator", variant="primary", id="auto_play_creator"),
                    Button("Get Alpaca Info", variant="primary", id="get_alpaca_info"),
                    Button("Market Data Compare", variant="primary", id="market_data_compare"),
                    classes="button-column",
                ),
                Container(
                    Button("View / Edit Current Plays", variant="primary", id="view_plays"),
                    Button("Upkeep and Status", variant="primary", id="system_status"),
                    Button("Configuration", variant="primary", id="configuration"),
                    Button("Open Chart", variant="primary", id="open_chart"),
                    Button("Trade Logger", variant="primary", id="trade_logger"),
                    classes="button-column",
                ),
                id="button_container"
            ),
            classes="container",
        )
        yield Footer()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle account selection changes"""
        import yaml
        import os
        from pathlib import Path

        selected_account = event.value
        current_active = config.get('alpaca', 'active_account')
        # If the selected account is the same as the currently active account, do nothing.
        if selected_account == current_active:
            return

        accounts = config.get('alpaca', 'accounts')
        nickname = accounts[selected_account].get('nickname', selected_account.replace('_', ' ').title())
        
        # Get the path to settings.yaml
        current_dir = os.path.dirname(os.path.abspath(__file__))
        settings_path = os.path.join(current_dir, 'config', 'settings.yaml')
        
        # Read the file content as lines
        with open(settings_path, 'r') as file:
            lines = file.readlines()
        
        # Find and replace the active_account line
        for i, line in enumerate(lines):
            if "active_account:" in line:
                # Preserve the indentation of the original line
                indent = len(line) - len(line.lstrip())
                lines[i] = " " * indent + f"active_account: '{selected_account}'  # Specify which account is currently active\n"
                break
        
        # Write the modified content back
        with open(settings_path, 'w') as file:
            file.writelines(lines)
        
        # Update the in-memory config immediately.
        # Since the config object isn't subscriptable, we try alternative approaches.
        try:
            # Try direct assignment (if config were subscriptable)
            config['alpaca']['active_account'] = selected_account
        except TypeError:
            # If the config object provides a setter method, use it.
            if hasattr(config, 'set'):
                config.set('alpaca', 'active_account', selected_account)
            # As another fallback, check if the config object holds the underlying
            # dictionary in an attribute (e.g., _config) and update that.
            elif hasattr(config, '_config'):
                config._config['alpaca']['active_account'] = selected_account
            else:
                # If none of these work, notify the user.
                self.notify("Warning: Unable to update in-memory configuration", severity="warning")
        
        # Notify using the nickname
        self.notify(f"Switched to {nickname}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create_play":
            self.run_play_creation_tool()
        elif event.button.id == "start_monitor":
            self.run_trading_monitor()
        elif event.button.id == "option_data_fetcher":
            self.run_option_data_fetcher()
        elif event.button.id == "view_plays":
            self.run_view_plays()
        elif event.button.id == "system_status":
            self.run_system_status()
        elif event.button.id == "configuration":
            self.run_configuration()
        elif event.button.id == "auto_play_creator":
            self.run_auto_play_creator()
        elif event.button.id == "open_chart":
            self.run_chart_viewer()
        elif event.button.id == "get_alpaca_info":
            self.run_get_alpaca_info()
        elif event.button.id == "trade_logger":
            self.run_trade_logger()
        elif event.button.id == "exit":
            self.app.exit()
        elif event.button.id == "market_data_compare":
            self.run_market_data_compare()

    def run_option_data_fetcher(self):
        tools_dir = os.path.join(os.path.dirname(__file__), "tools")
        script_path = os.path.join(tools_dir, "option_data_fetcher.py")
        if os.name == 'nt':  # Windows
            subprocess.Popen(['cmd', '/k', 'python', script_path], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:  # Unix-like systems
            subprocess.Popen(['gnome-terminal', '--', 'python', script_path])

    def run_play_creation_tool(self):
        try:
            # Get absolute paths
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tools_dir = os.path.join(current_dir, "tools")
            
            if os.name == 'nt':  # Windows
                # Create the command without string interpolation
                cmd = ['cmd', '/k', 'cd', '/d', tools_dir, '&', 'python', 'play-creation-tool.py']
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:  # Unix-like systems
                subprocess.Popen(['gnome-terminal', '--', 'python', 'play-creation-tool.py'], 
                               cwd=tools_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_trading_monitor(self):
        try:
            if os.name == 'nt':  # Windows
                # Check if running as admin
                running_as_admin = is_admin()
                
                # Ask user for preference if not admin
                if not running_as_admin:
                    self.app.push_screen(AdminChoiceScreen())
                    return
                
                # If running as admin, launch directly
                current_dir = os.path.dirname(os.path.abspath(__file__))
                package_root = os.path.dirname(current_dir)
                cmd = [
                    'cmd', '/c', 
                    'start', 
                    'GoldFlipper Trading System',
                    '/D', package_root,
                    'cmd', '/k',
                    'python', '-m', 'goldflipper.run', '--mode', 'console'
                ]
                self.app.exit()
                subprocess.run(cmd, check=True)
                
            else:  # Unix-like systems
                self.app.exit()
                subprocess.Popen(['gnome-terminal', '--', 'python', '-m', 'goldflipper.run', '--mode', 'console'])
                
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_view_plays(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tools_dir = os.path.join(current_dir, "tools")
            
            if os.name == 'nt':  # Windows
                cmd = ['cmd', '/k', 'cd', '/d', tools_dir, '&', 'python', 'view_plays.py']
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:  # Unix-like systems
                subprocess.Popen(['gnome-terminal', '--', 'python', 'view_plays.py'], 
                               cwd=tools_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_system_status(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tools_dir = os.path.join(current_dir, "tools")
            
            if os.name == 'nt':  # Windows
                cmd = ['cmd', '/k', 'cd', '/d', tools_dir, '&', 'python', 'system_status.py']
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:  # Unix-like systems
                subprocess.Popen(['gnome-terminal', '--', 'python', 'system_status.py'], 
                               cwd=tools_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_configuration(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tools_dir = os.path.join(current_dir, "tools")
            
            if os.name == 'nt':  # Windows
                cmd = ['cmd', '/k', 'cd', '/d', tools_dir, '&', 'python', 'configuration.py']
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:  # Unix-like systems
                subprocess.Popen(['gnome-terminal', '--', 'python', 'configuration.py'], 
                               cwd=tools_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_auto_play_creator(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tools_dir = os.path.join(current_dir, "tools")
            
            if os.name == 'nt':  # Windows
                cmd = ['cmd', '/k', 'cd', '/d', tools_dir, '&', 'python', 'auto_play_creator.py']
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:  # Unix-like systems
                subprocess.Popen(['gnome-terminal', '--', 'python', 'auto_play_creator.py'], 
                               cwd=tools_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_chart_viewer(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            chart_dir = os.path.join(current_dir, "chart")
            
            if os.name == 'nt':  # Windows
                cmd = ['cmd', '/k', 'cd', '/d', chart_dir, '&', 'python', 'chart_viewer.py']
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:  # Unix-like systems
                subprocess.Popen(['gnome-terminal', '--', 'python', 'chart_viewer.py'], 
                               cwd=chart_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_get_alpaca_info(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tools_dir = os.path.join(current_dir, "tools")
            
            if os.name == 'nt':  # Windows
                cmd = ['cmd', '/k', 'cd', '/d', tools_dir, '&', 'python', 'get_alpaca_info.py']
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:  # Unix-like systems
                subprocess.Popen(['gnome-terminal', '--', 'python', 'get_alpaca_info.py'], 
                               cwd=tools_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_trade_logger(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            logging_dir = os.path.join(current_dir, "logging")
            
            if os.name == 'nt':  # Windows
                cmd = ['cmd', '/k', 'cd', '/d', logging_dir, '&', 'python', 'trade_logger_ui.py']
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:  # Unix-like systems
                subprocess.Popen(['gnome-terminal', '--', 'python', 'trade_logger_ui.py'], 
                               cwd=logging_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_market_data_compare(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tools_dir = os.path.join(current_dir, "tools")
            
            if os.name == 'nt':  # Windows
                cmd = ['cmd', '/k', 'cd', '/d', tools_dir, '&', 'python', 'multi_market_data.py']
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:  # Unix-like systems
                subprocess.Popen(['gnome-terminal', '--', 'python', 'multi_market_data.py'], 
                               cwd=tools_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

class GoldflipperTUI(App):
    CSS = """
    Screen {
        align: center middle;
        background: $surface;
    }

    #header_container {
        width: 100%;
        height: auto;
        align: center middle;
        margin: 1 1 2 1;
    }

    #welcome {
        width: 65%;
        height: auto;
        margin: 1;
        padding: 1;
        text-align: center;
        color: gold;
        background: $surface;
        text-style: bold;
        border: heavy $accent;
    }
    
    #account_selector {
        width: 35%;
        height: 5;
        margin: 1;
        padding: 0;
        background: $surface;
        border: heavy $accent;
        color: gold;
    }

    #account_selector > .select--option {
        padding: 0;
        height: auto;
    }

    #account_selector > .select--container {
        padding: 0;
        height: auto;
    }

    #account_selector > .select--placeholder {
        padding: 0;
        height: auto;
    }

    #account_selector:focus {
        border: heavy $accent;
    }
    
    .container {
        width: 90%;
        height: auto;
        align: center middle;
        background: $surface-darken-2;
        border: panel $primary;
        padding: 2;
        margin-top: 1;
    }

    #button_container {
        width: 100%;
        height: auto;
        align: center middle;
        padding: 1;
    }
    
    .button-column {
        width: 50%;
        height: auto;
        align: center middle;
        padding: 1;
    }
    
    Button {
        width: 30;
        margin: 1;
    }

    Button.success {
        background: #2ea043;
        color: white;
    }

    Button.success:hover {
        background: #3fb950;
    }

    Button:hover {
        background: $accent;
    }

    #dialog-container {
        width: 60%;
        height: auto;
        align: center middle;
        background: $surface-darken-2;
        border: heavy $accent;
        padding: 1;
        margin: 1;
        offset: 30% 20%;
    }
    
    #dialog-message {
        width: 100%;
        height: auto;
        content-align: center middle;
        padding: 1;
        margin: 1;
    }
    
    .dialog-buttons {
        width: 100%;
        height: auto;
        align: center middle;
        padding: 1;
        margin: 1;
    }
    
    .dialog-buttons Button {
        margin: 1 2;
        min-width: 16;
    }
    
    Button.warning {
        background: #d29922;
        color: $text;
    }
    
    Button.warning:hover {
        background: #e8aa25;
    }
    
    Button.error {
        background: #a82320;
        color: $text;
    }
    
    Button.error:hover {
        background: #bc2724;
    }

    AdminChoiceScreen {
        align: center middle;
    }
    
    #dialog-container {
        width: 60%;
        background: $surface-darken-2;
        border: heavy $accent;
        padding: 1;
        margin: 1;
    }
    
    #dialog-message {
        text-align: center;
        padding: 1;
        margin: 1;
    }
    
    .dialog-buttons {
        layout: horizontal;
        align: center middle;
        padding: 1;
        margin: 1;
    }
    
    .dialog-buttons Button {
        margin: 1 2;
        min-width: 16;
    }
    """

    def on_mount(self) -> None:
        self.push_screen(WelcomeScreen())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses for admin choice"""
        try:
            if event.button.id == "continue_regular":
                # Remove the dialog first
                self.query("#dialog-container").remove()
                # Then launch the system
                current_dir = os.path.dirname(os.path.abspath(__file__))
                package_root = os.path.dirname(current_dir)
                self.launch_trading_system(package_root)
            elif event.button.id == "restart_admin":
                # Remove the dialog first
                self.query("#dialog-container").remove()
                # Then restart as admin
                current_dir = os.path.dirname(os.path.abspath(__file__))
                package_root = os.path.dirname(current_dir)
                cmd = ['powershell', 'Start-Process', 'python', '-ArgumentList',
                       f'"-m goldflipper.run --mode console"',
                       '-Verb', 'RunAs', '-WorkingDirectory', package_root]
                subprocess.run(cmd)
                self.app.exit()
            elif event.button.id == "cancel":
                # Just remove the dialog
                self.query("#dialog-container").remove()
        except Exception as e:
            self.notify(f"Error handling button press: {str(e)}", severity="error")

if __name__ == "__main__":
    app = GoldflipperTUI()
    app.run()