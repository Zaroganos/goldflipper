from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Button, Static, Select
from textual.screen import Screen
import subprocess
import sys
import os
from pathlib import Path
from goldflipper.config.config import config
import yaml

class WelcomeScreen(Screen):
    BINDINGS = [("q", "quit", "Quit")]
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Horizontal(
                Static(" Welcome to Goldflipper ", id="welcome"),
                Select(
                    [(acc.get('nickname', name.replace('_', ' ').title()), name) 
                     for name, acc in config.get('alpaca', 'accounts').items() 
                     if acc.get('enabled', False)],
                    prompt="Select Trading Account",
                    id="account_selector"
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
        yield Static("Trading System: Unknown", id="trading_system_status")
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(5, self.refresh_system_status)

    def refresh_system_status(self) -> None:
        from goldflipper.utils import trading_system_status
        is_running = trading_system_status.is_trading_system_running()
        status_text = "Running" if is_running else "Not Running"
        widget = self.query_one("#trading_system_status", Static)
        widget.update(f"Trading System: {status_text}")

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle account selection changes"""
        import yaml
        import os
        from pathlib import Path

        selected_account = event.value
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
                cmd = 'python -m goldflipper.run'
                subprocess.Popen(['cmd', '/k', cmd],
                               creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:  # Unix-like systems
                subprocess.Popen(['gnome-terminal', '--', 'python', '-m', 'goldflipper.run'])
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
    """

    def on_mount(self) -> None:
        self.push_screen(WelcomeScreen())

if __name__ == "__main__":
    app = GoldflipperTUI()
    app.run()