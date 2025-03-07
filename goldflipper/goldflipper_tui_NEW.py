from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Button, Static, Select, Input, Switch, Checkbox, RadioSet, RadioButton, Label, OptionList
from textual.screen import Screen
import subprocess
import sys
import os
import time
from pathlib import Path
from goldflipper.config.config import config, settings_just_created, reset_settings_created_flag
import yaml
import asyncio  # Added for asyncio.to_thread
from textual.widgets.option_list import Option
from textual.containers import Container, Horizontal, Vertical, Grid, ScrollableContainer

class ConfigChoiceScreen(Screen):
    """Screen that presents the user with configuration options."""
    
    BINDINGS = [("escape", "app.pop_screen", "Back")]
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("Select Configuration Mode", id="config_title"),
            Container(
                Button("Graphical Configuration", variant="primary", id="graphical_config"),
                Button("YAML Text Mode (Advanced)", variant="warning", id="yaml_config"),
                id="config_buttons",
            ),
            id="config_container",
        )
        yield Footer()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses in the config choice screen."""
        button_id = event.button.id
        
        if button_id == "graphical_config":
            # Will implement the graphical configuration screen later
            self.app.push_screen("graphical_config")
        elif button_id == "yaml_config":
            # Use the existing YAML text editor
            welcome_screen = self.app.get_screen("welcome")
            welcome_screen.run_yaml_configuration()
            self.app.pop_screen()

class ConfirmationScreen(Screen):
    BINDINGS = [("q", "quit", "Cancel")]

    def __init__(self, message: str, on_confirm, **kwargs):
        super().__init__(**kwargs)
        self.message = message
        self.on_confirm = on_confirm

    def compose(self) -> ComposeResult:
        yield Static(self.message, id="confirmation_message")
        yield Static("Press Y to confirm, N to cancel", id="confirmation_instructions")

    def on_key(self, event) -> None:
        if event.key.lower() == "y":
            self.on_confirm()
            self.app.pop_screen()
        elif event.key.lower() == "n":
            self.app.pop_screen()

class WelcomeScreen(Screen):
    BINDINGS = [("q", "quit", "Quit")]
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        # Use the global flag from config module to determine if settings file was just created
        current_dir = os.path.dirname(os.path.abspath(__file__))
        settings_path = os.path.join(current_dir, 'config', 'settings.yaml')
        
        # Set button variants based on whether settings were just created
        launch_variant = "primary" if settings_just_created else "success"
        config_variant = "success" if settings_just_created else "primary"
        
        # Debug print to confirm path and existence
        print(f"\n\nDEBUG: Settings path: {settings_path}")
        print(f"DEBUG: Settings exists: {os.path.exists(settings_path)}")
        print(f"DEBUG: Settings just created: {settings_just_created}")
        print(f"DEBUG: Current directory: {current_dir}\n\n")
        
        # Determine active account to show its nickname as the prompt if available.
        active_prompt = "Select Trading Account"
        try:
            active_account = config.get('alpaca', 'active_account')
            if active_account and active_account in config.get('alpaca', 'accounts', {}):
                account_info = config.get('alpaca', 'accounts')[active_account]
                if account_info.get('enabled', False):
                    active_prompt = account_info.get('nickname', active_account.replace('_', ' ').title())
            
            account_options = [(acc.get('nickname', name.replace('_', ' ').title()), name)
                       for name, acc in config.get('alpaca', 'accounts', {}).items()
                       if acc.get('enabled', False)]
        except Exception as e:
            # If config can't be loaded, use empty account list
            account_options = []
        
        yield Container(
            Horizontal(
                Static(" Welcome to Goldflipper ", id="welcome"),
                Select(
                    account_options if account_options else [("No Accounts Available", "none")],
                    prompt=active_prompt,
                    id="account_selector"
                ),
                id="header_container"
            ),
            Horizontal(
                Container(
                    Button("Create New Play", variant="primary", id="create_play"),
                    Button("Fetch Option Data", variant="primary", id="option_data_fetcher"),
                    Button("Launch Trading System", variant=launch_variant, id="start_monitor"),
                    Button("Auto Play Creator", variant="primary", id="auto_play_creator"),
                    Button("Get Alpaca Info", variant="primary", id="get_alpaca_info"),
                    # Button("Market Data Compare", variant="primary", id="market_data_compare"),  # Temporarily commented out
                    Button("Upload Template", variant="primary", id="upload_template"),
                    classes="button-column",
                ),
                Container(
                    Button("View / Edit Current Plays", variant="primary", id="view_plays"),
                    Button("Upkeep and Status", variant="primary", id="system_status"),
                    Button("Configuration", variant=config_variant, id="configuration"),
                    Button("Open Chart", variant="primary", id="open_chart"),
                    Button("Trade Logger", variant="primary", id="trade_logger"),
                    Button("Manage Service", variant="warning", id="manage_service"),
                    classes="button-column",
                ),
                id="button_container"
            ),
            classes="container",
        )
        yield Footer()

    async def on_mount(self) -> None:
        # Transition the welcome text after 3 seconds
        self.set_timer(3, self.transition_to_status)
        # Update the connection status (and update periodically every 60 seconds)
        await self.update_connection_status()
        self.set_interval(60, lambda: self.call_later(self.update_connection_status))
        
        # Check if settings were just created using the global flag
        if settings_just_created:
            self.notify(
                "Welcome to GoldFlipper! Your settings file has been created. Please configure your settings before launching the trading system.",
                title="New Configuration Created",
                timeout=10,
                severity="information"
            )

    async def update_connection_status(self) -> None:
        """
        Check the connection status using test_alpaca_connection,
        then update the account selector by replacing it with a new instance.
        This new instance will show the active account connection status.
        """
        import asyncio, os, yaml
        from goldflipper.tools.get_alpaca_info import test_alpaca_connection

        # Try to import Option (with fallback).
        try:
            from textual.widgets.select import Option
        except ImportError:
            from collections import namedtuple
            Option = namedtuple("Option", ["label", "value"])

        # Force a reset of the Alpaca client.
        try:
            from goldflipper.alpaca_client import reset_client
            reset_client()
        except Exception as e:
            self.notify(f"Error resetting Alpaca client: {e}")

        # Reload updated configuration.
        try:
            config.reload()
        except Exception as e:
            self.notify(f"Error reloading config: {e}")

        active_account_config = config.get('alpaca', 'active_account')

        current_dir = os.path.dirname(os.path.abspath(__file__))
        settings_path = os.path.join(current_dir, 'config', 'settings.yaml')
        try:
            with open(settings_path, 'r') as file:
                file_config = yaml.safe_load(file)
            _ = file_config.get('alpaca', {}).get('active_account', 'unknown')
        except Exception as e:
            self.notify(f"Error reading settings file: {e}")

        try:
            _ = config.get('alpaca', 'accounts')[active_account_config]
        except Exception as e:
            return

        # Run the connection test in a background thread.
        connection_status, _ = await asyncio.to_thread(test_alpaca_connection)

        # Build the options list with updated connection status.
        accounts = config.get('alpaca', 'accounts')
        new_options = []
        for name, acc in accounts.items():
            account_nickname = acc.get('nickname', name.replace('_', ' ').title())
            if name == active_account_config:
                if connection_status:
                    display_label = f"[green]Connected:[/green] {account_nickname}"
                else:
                    display_label = f"[red]Not Connected:[/red] {account_nickname}"
            else:
                display_label = account_nickname
            new_options.append(Option(label=display_label, value=name))

        # Determine the label for the currently selected account.
        selected_label = ""
        for option in new_options:
            if option.value == active_account_config:
                selected_label = option.label
                break

        from textual.widgets import Select
        try:
            old_select = self.query_one("#account_selector", Select)
        except Exception as e:
            return

        parent_container = old_select.parent
        old_select.remove()
        await asyncio.sleep(0.05)

        new_select = Select(
            options=new_options,
            prompt=selected_label,
            id="account_selector"
        )
        new_select.value = active_account_config

        parent_container.mount(new_select)
        await asyncio.sleep(0)
        new_select.refresh()

    def transition_to_status(self) -> None:
        """Fade out the welcome text then update it with trading system status."""
        welcome_widget = self.query_one("#welcome", Static)
        welcome_widget.add_class("faded")
        self.set_timer(0.6, lambda: self.update_welcome_with_status(welcome_widget))

    def update_welcome_with_status(self, widget: Static) -> None:
        from goldflipper.utils import trading_system_status
        is_running = trading_system_status.is_trading_system_running()
        status_text = "[green]Trading System: Running[/green]" if is_running else "[red]Trading System: Not Running[/red]"
        widget.update(f" {status_text} ")
        widget.remove_class("faded")
        self.set_interval(5, self.refresh_status_in_welcome)

    def refresh_status_in_welcome(self) -> None:
        from goldflipper.utils import trading_system_status
        is_running = trading_system_status.is_trading_system_running()
        status_text = "[green]Trading System: Running[/green]" if is_running else "[red]Trading System: Not Running[/red]"
        widget = self.query_one("#welcome", Static)
        widget.update(f" {status_text} ")

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle account selection changes"""
        import os
        import asyncio

        selected_account = event.value
        accounts = config.get('alpaca', 'accounts')
        nickname = accounts[selected_account].get('nickname', selected_account.replace('_', ' ').title())

        # Get the path to settings.yaml
        current_dir = os.path.dirname(os.path.abspath(__file__))
        settings_path = os.path.join(current_dir, 'config', 'settings.yaml')

        # Read the file content as lines and update the active_account.
        with open(settings_path, 'r') as file:
            lines = file.readlines()
        for i, line in enumerate(lines):
            if "active_account:" in line:
                indent = len(line) - len(line.lstrip())
                lines[i] = " " * indent + f"active_account: '{selected_account}'  # Specify which account is currently active\n"
                break
        with open(settings_path, 'w') as file:
            file.writelines(lines)

        # Immediately reset the client
        try:
            from goldflipper.alpaca_client import reset_client
            reset_client()
        except Exception as e:
            self.notify(f"Error resetting client: {e}")

        # Reload the configuration so we get the updated active_account.
        try:
            config.reload()
        except Exception as e:
            self.notify(f"Error reloading config: {e}")

        self.active_account = selected_account
        self.active_account_nickname = nickname

        select_widget = self.query_one("#account_selector", Select)
        select_widget.prompt = f"[yellow]Connecting...[/yellow] {nickname}"
        select_widget.refresh()

        self.notify(f"Switched to {nickname}")
        asyncio.create_task(self.update_connection_status())

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
        #elif event.button.id == "market_data_compare":
        #    self.run_market_data_compare()
        elif event.button.id == "manage_service":
            self.run_manage_service()
        elif event.button.id == "upload_template":
            self.run_upload_template()

    def run_manage_service(self) -> None:
        """
        Check if the service is installed and prompt the user to install or uninstall.
        When confirmed, launch an elevated process using PowerShell so that UAC is triggered.
        """
        import os
        import subprocess
        if os.name != 'nt':
            self.notify("Service management is available on Windows only.")
            return

        try:
            import win32serviceutil
            # If QueryServiceStatus succeeds, the service is installed.
            win32serviceutil.QueryServiceStatus("GoldFlipperService")
            service_installed = True
        except Exception:
            service_installed = False

        if service_installed:
            message = (
                "You are about to STOP and UNINSTALL the GoldFlipper Service.\n"
                "This will stop the running service and uninstall it.\n"
                "This requires administrative privileges and will launch an elevated process.\n"
                "Note: Changes made will not take effect until you reboot.\n"
                "Do you want to proceed? (Y/N)"
            )
            mode = "remove"
        else:
            message = (
                "You are about to INSTALL the Goldflipper Service and automatically start it.\n"
                "This requires administrative privileges and will launch an elevated process.\n"
                "Note: Changes made will not take effect until you reboot.\n"
                "Do you want to proceed? (Y/N)"
            )
            mode = "install"

        def perform_action():
            if mode == "install":
                final_command = (
                    "python -m goldflipper.run --mode install; Start-Sleep -Seconds 2; net start GoldFlipperService"
                )
            else:
                final_command = "net stop GoldFlipperService; python -m goldflipper.run --mode remove"
            ps_command = f"Start-Process powershell -ArgumentList '-NoProfile -Command \"{final_command}\"' -Verb RunAs"
            subprocess.Popen(["powershell", "-Command", ps_command])
            self.notify(f"{'Uninstallation' if service_installed else 'Installation'} initiated. Changes will require a reboot to apply.")

        self.app.push_screen(ConfirmationScreen(message, perform_action))

    def run_option_data_fetcher(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tools_dir = os.path.join(current_dir, "tools")
            if os.name == 'nt':  # Windows
                cmd = ['cmd', '/k', 'cd', '/d', tools_dir, '&', 'python', 'option_data_fetcher.py']
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:  # Unix-like systems
                subprocess.Popen(['gnome-terminal', '--', 'python', 'option_data_fetcher.py'], cwd=tools_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_play_creation_tool(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tools_dir = os.path.join(current_dir, "tools")
            if os.name == 'nt':
                cmd = ['cmd', '/k', 'cd', '/d', tools_dir, '&', 'python', 'play_creation_tool.py']
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(['gnome-terminal', '--', 'python', 'play_creation_tool.py'], cwd=tools_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_trading_monitor(self):
        try:
            if os.name == 'nt':
                cmd = ['cmd', '/k', 'python', '-m', 'goldflipper.run']
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(['gnome-terminal', '--', 'python', '-m', 'goldflipper.run'])
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_view_plays(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tools_dir = os.path.join(current_dir, "tools")
            if os.name == 'nt':
                cmd = ['cmd', '/k', 'cd', '/d', tools_dir, '&', 'python', 'view_plays.py']
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(['gnome-terminal', '--', 'python', 'view_plays.py'], cwd=tools_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_system_status(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tools_dir = os.path.join(current_dir, "tools")
            if os.name == 'nt':
                cmd = ['cmd', '/k', 'cd', '/d', tools_dir, '&', 'python', 'system_status.py']
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(['gnome-terminal', '--', 'python', 'system_status.py'], cwd=tools_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_configuration(self):
        """
        Show the configuration choice screen.
        """
        self.app.push_screen("config_choice")

    def run_yaml_configuration(self):
        """
        Launch the configuration tool to edit settings.yaml using a text editor.
        """
        from goldflipper.tools.configuration import open_settings
        import importlib
        import sys
        
        try:
            # Check if this was the first run with a newly created settings file
            was_first_run = settings_just_created
            
            # Launch the configuration editor
            config_result = open_settings()
            
            if config_result:
                # Reload the config module to pick up changes
                importlib.reload(sys.modules['goldflipper.config.config'])
                
                # If this was the first configuration, update the button colors
                if was_first_run:
                    # Reset the settings created flag to avoid showing notifications again
                    reset_settings_created_flag()
                    
                    # Find and update the Launch Trading System button
                    launch_button = self.query_one("#start_monitor", Button)
                    launch_button.variant = "success"
                    
                    # Find and update the Configuration button
                    config_button = self.query_one("#configuration", Button)
                    config_button.variant = "primary"
                    
                    self.notify(
                        "Configuration completed! You're ready to launch the trading system.",
                        title="Setup Complete",
                        timeout=5,
                        severity="success"
                    )
            
            # Always refresh the UI to show latest account information
            self.refresh_status_in_welcome()
            
        except Exception as e:
            self.notify(f"Error launching configuration tool: {e}", severity="error")

    def run_auto_play_creator(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tools_dir = os.path.join(current_dir, "tools")
            if os.name == 'nt':
                cmd = ['cmd', '/k', 'cd', '/d', tools_dir, '&', 'python', 'auto_play_creator.py']
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(['gnome-terminal', '--', 'python', 'auto_play_creator.py'], cwd=tools_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_chart_viewer(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            chart_dir = os.path.join(current_dir, "chart")
            if os.name == 'nt':
                cmd = ['cmd', '/k', 'cd', '/d', chart_dir, '&', 'python', 'chart_viewer.py']
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(['gnome-terminal', '--', 'python', 'chart_viewer.py'], cwd=chart_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_get_alpaca_info(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tools_dir = os.path.join(current_dir, "tools")
            if os.name == 'nt':
                cmd = ['cmd', '/k', 'cd', '/d', tools_dir, '&', 'python', 'get_alpaca_info.py']
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(['gnome-terminal', '--', 'python', 'get_alpaca_info.py'], cwd=tools_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_trade_logger(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            logging_dir = os.path.join(current_dir, "logging")
            if os.name == 'nt':
                cmd = ['cmd', '/k', 'cd', '/d', logging_dir, '&', 'python', 'trade_logger_ui.py']
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(['gnome-terminal', '--', 'python', 'trade_logger_ui.py'], cwd=logging_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_upload_template(self) -> None:
        """
        Prompts the user to select a CSV file and launches the CSV ingestion tool.
        The tool processes the file and saves resulting plays to the New and Temp folders.
        """
        import os
        import subprocess

        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()  # Hide the root window.
            file_path = filedialog.askopenfilename(
                title="Select CSV Template",
                filetypes=[("CSV Files", "*.csv")]
            )
            root.destroy()
        except Exception as e:
            self.notify(f"File dialog error: {e}")
            file_path = input("Enter CSV file path: ").strip()

        if not file_path:
            self.notify("No file selected, upload aborted.")
            return

        # Assume the CSV ingestion tool is located in the 'tools' subfolder.
        current_dir = os.path.dirname(os.path.abspath(__file__))
        tools_dir = os.path.join(current_dir, "tools")

        if os.name == "nt":  # Windows
            cmd = [
                "cmd", "/k", "python",
                os.path.join(tools_dir, "play-csv-ingestion-tool.py"),
                file_path
            ]
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:  # Unix-like systems
            cmd = [
                "gnome-terminal", "--", "python3",
                os.path.join(tools_dir, "play-csv-ingestion-tool.py"),
                file_path
            ]
            subprocess.Popen(cmd, cwd=tools_dir)

'''
    def run_market_data_compare(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tools_dir = os.path.join(current_dir, "tools")
            if os.name == 'nt':
                cmd = ['cmd', '/k', 'cd', '/d', tools_dir, '&', 'python', 'multi_market_data.py']
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(['gnome-terminal', '--', 'python', 'multi_market_data.py'], cwd=tools_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")
'''

class GraphicalConfigScreen(Screen):
    """Graphical configuration screen for editing settings.yaml"""
    
    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("ctrl+s", "save_settings", "Save Settings"),
    ]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.settings = {}
        self.modified = False
        self.sections = {
            "alpaca": "Alpaca API Settings",
            "market_data": "Market Data Settings",
            "options_swings": "Options Strategy Settings",
            "monitoring": "Play Monitoring",
            "orders": "Order Settings",
            "market_hours": "Market Hours",
            "auto_play_creator": "Auto Play Creator",
            "chart_viewer": "Chart Viewer Settings",
        }
        self.current_section = "alpaca"
        
    def compose(self) -> ComposeResult:
        """Compose the graphical configuration screen."""
        yield Header(show_clock=True)
        yield Container(
            Container(
                Static("Graphical Configuration", id="config_title"),
                id="title_container"
            ),
            Horizontal(
                Container(
                    # Navigation sidebar with sections
                    *(Button(name, id=f"nav_{section}", variant="primary") 
                      for section, name in self.sections.items()),
                    id="nav_sidebar",
                ),
                # Main content area with settings
                ScrollableContainer(
                    id="settings_container"
                ),
                id="config_layout"
            ),
            Horizontal(
                Button("Save Settings", variant="success", id="save_button"),
                Button("Cancel", variant="error", id="cancel_button"),
                id="action_buttons"
            ),
            id="config_main_container"
        )
        yield Footer()
        
    def on_mount(self) -> None:
        """Load settings when the screen is mounted."""
        self.load_settings()
        self.display_section("alpaca")
        
    def action_go_back(self) -> None:
        """Handle escape key to go back."""
        if self.modified:
            self.app.push_screen(
                ConfirmationScreen(
                    "You have unsaved changes. Discard changes?",
                    self.discard_changes
                )
            )
        else:
            self.app.pop_screen()
            
    def discard_changes(self) -> None:
        """Discard changes and go back."""
        self.app.pop_screen()
            
    def action_save_settings(self) -> None:
        """Save settings when Ctrl+S is pressed."""
        self.save_settings()
        
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        
        if button_id == "save_button":
            self.save_settings()
        elif button_id == "cancel_button":
            self.action_go_back()
        elif button_id.startswith("nav_"):
            section = button_id[4:]  # Remove 'nav_' prefix
            self.display_section(section)
            
    def load_settings(self) -> None:
        """Load settings from the YAML file."""
        try:
            import yaml
            import os
            
            current_dir = os.path.dirname(os.path.abspath(__file__))
            settings_path = os.path.join(current_dir, 'config', 'settings.yaml')
            
            with open(settings_path, 'r') as f:
                self.settings = yaml.safe_load(f)
                
            self.notify("Settings loaded successfully", severity="information")
        except Exception as e:
            self.notify(f"Error loading settings: {e}", severity="error")
            
    def save_settings(self) -> None:
        """Save settings to the YAML file."""
        try:
            import yaml
            import os
            from goldflipper.config.config import reset_settings_created_flag
            import importlib
            import sys
            
            # Get values from form fields and update self.settings
            self.update_settings_from_form()
            
            current_dir = os.path.dirname(os.path.abspath(__file__))
            settings_path = os.path.join(current_dir, 'config', 'settings.yaml')
            
            # Preserve comments and formatting by reading the original file
            with open(settings_path, 'r') as f:
                original_content = f.read()
                
            # Parse the original content to get comments
            lines = original_content.splitlines()
            comments = {}
            
            # Extract comments
            line_num = 0
            section_comment_lines = []
            last_key = None
            
            for i, line in enumerate(lines):
                if line.strip().startswith("#"):
                    section_comment_lines.append(line)
                elif ":" in line and not line.strip().startswith("-"):
                    key = line.split(":", 1)[0].strip()
                    if section_comment_lines:
                        comments[key] = section_comment_lines
                        section_comment_lines = []
                    last_key = key
                elif last_key and (line.strip().startswith("-") or line.strip() == ""):
                    continue
                else:
                    section_comment_lines = []
                    
            # Write the updated settings with preserved comments
            with open(settings_path, 'w') as f:
                # Add file header comment if it exists
                if "" in comments:
                    f.write("\n".join(comments[""]) + "\n\n")
                    
                # Write settings with their comments
                yaml.dump(self.settings, f, default_flow_style=False, sort_keys=False)
                
            # Reload the config module to pick up changes
            importlib.reload(sys.modules['goldflipper.config.config'])
            
            # Check if this was the first run with newly created settings
            was_first_run = settings_just_created
            if was_first_run:
                reset_settings_created_flag()
                
                # Update button colors on welcome screen
                welcome_screen = self.app.get_screen("welcome")
                launch_button = welcome_screen.query_one("#start_monitor", Button)
                launch_button.variant = "success"
                config_button = welcome_screen.query_one("#configuration", Button)
                config_button.variant = "primary"
                
            self.modified = False
            welcome_screen = self.app.get_screen("welcome")
            welcome_screen.refresh_status_in_welcome()
            
            self.notify("Settings saved successfully", severity="success")
        except Exception as e:
            self.notify(f"Error saving settings: {e}", severity="error")
            
    def update_settings_from_form(self) -> None:
        """Update settings dictionary from form fields."""
        if self.current_section == "alpaca":
            self.update_alpaca_settings()
        elif self.current_section == "market_data":
            self.update_market_data_settings()
        elif self.current_section == "options_swings":
            self.update_options_swings_settings()
        elif self.current_section == "monitoring":
            self.update_monitoring_settings()
        elif self.current_section == "orders":
            self.update_orders_settings()
        elif self.current_section == "market_hours":
            self.update_market_hours_settings()
        elif self.current_section == "auto_play_creator":
            self.update_auto_play_creator_settings()
        elif self.current_section == "chart_viewer":
            self.update_chart_viewer_settings()
            
    def update_alpaca_settings(self) -> None:
        """Update Alpaca API settings from form fields."""
        try:
            # Get account selections
            active_account = self.query_one("#select_active_account", Select).value
            
            # Update active account in settings
            self.settings["alpaca"]["active_account"] = active_account
            
            # For each account, update enabled status and credentials
            accounts = self.settings.get("alpaca", {}).get("accounts", {})
            for account_name in accounts:
                # Update enabled status
                try:
                    enabled_switch = self.query_one(f"#switch_enabled_{account_name}", Switch)
                    accounts[account_name]["enabled"] = enabled_switch.value
                except Exception:
                    pass  # Switch might not exist if account was not displayed
                
                # Update nickname
                try:
                    nickname_input = self.query_one(f"#input_nickname_{account_name}", Input)
                    accounts[account_name]["nickname"] = nickname_input.value
                except Exception:
                    pass
                
                # Update API key
                try:
                    api_key_input = self.query_one(f"#input_api_key_{account_name}", Input)
                    accounts[account_name]["api_key"] = api_key_input.value
                except Exception:
                    pass
                
                # Update secret key
                try:
                    secret_key_input = self.query_one(f"#input_secret_key_{account_name}", Input)
                    accounts[account_name]["secret_key"] = secret_key_input.value
                except Exception:
                    pass
                
            self.modified = True
        except Exception as e:
            self.notify(f"Error updating Alpaca settings: {e}", severity="error")
            
    def update_market_data_settings(self) -> None:
        """Update market data settings from form fields."""
        try:
            # Basic market data settings
            interval = self.query_one("#input_market_data_interval", Input).value
            period = self.query_one("#input_market_data_period", Input).value
            
            self.settings["market_data"]["interval"] = interval
            self.settings["market_data"]["period"] = period
            
            # Option chain display settings
            columns_str = self.query_one("#input_option_chain_columns", Input).value
            default_columns = [col.strip() for col in columns_str.split(",") if col.strip()]
            self.settings["market_data"]["option_chain_display"]["default_columns"] = default_columns
            
            # Greeks settings
            greeks_enabled = self.query_one("#switch_greeks_enabled", Switch).value
            greek_columns_str = self.query_one("#input_greek_columns", Input).value
            greek_columns = [col.strip() for col in greek_columns_str.split(",") if col.strip()]
            
            self.settings["market_data"]["option_chain_display"]["greeks"]["enabled"] = greeks_enabled
            self.settings["market_data"]["option_chain_display"]["greeks"]["columns"] = greek_columns
            
            self.modified = True
        except Exception as e:
            self.notify(f"Error updating market data settings: {e}", severity="error")
            
    def display_market_data_settings(self, container: ScrollableContainer) -> None:
        """Display market data settings."""
        market_data = self.settings.get("market_data", {})
        
        # Basic market data settings
        basic_container = Container(id="basic_market_data_container")
        container.mount(basic_container)  # Mount to parent first
        
        basic_container.mount(Static("Basic Market Data Settings", classes="subsection_title"))
        basic_container.mount(Horizontal(
            Label("Interval:"),
            Input(value=market_data.get("interval", "1m"), id="input_market_data_interval"),
            id="market_data_interval_row"
        ))
        basic_container.mount(Horizontal(
            Label("Period:"),
            Input(value=market_data.get("period", "1d"), id="input_market_data_period"),
            id="market_data_period_row"
        ))
        
        # Option chain display settings
        option_chain = market_data.get("option_chain_display", {})
        
        option_chain_container = Container(id="option_chain_container")
        container.mount(option_chain_container)  # Mount to parent first
        
        option_chain_container.mount(Static("Option Chain Display", classes="subsection_title"))
        
        # Default columns
        default_columns = option_chain.get("default_columns", [])
        columns_value = ", ".join(default_columns)
        option_chain_container.mount(Horizontal(
            Label("Default Columns:"),
            Input(value=columns_value, id="input_option_chain_columns"),
            id="option_chain_columns_row"
        ))
        
        # Greeks display settings
        greeks = option_chain.get("greeks", {})
        
        greeks_container = Container(id="greeks_container")
        container.mount(greeks_container)  # Mount to parent first
        
        greeks_container.mount(Static("Greeks Settings", classes="subsection_title"))
        greeks_container.mount(Horizontal(
            Label("Enabled:"),
            Switch(value=greeks.get("enabled", True), id="switch_greeks_enabled"),
            id="greeks_enabled_row"
        ))
        
        # Greek columns
        greek_columns = greeks.get("columns", [])
        greek_columns_value = ", ".join(greek_columns)
        greeks_container.mount(Horizontal(
            Label("Greek Columns:"),
            Input(value=greek_columns_value, id="input_greek_columns"),
            id="greek_columns_row"
        ))

    def update_options_swings_settings(self) -> None:
        """Update options swings settings from form fields."""
        options_swings = self.settings.get("options_swings", {})
        
        # Basic settings
        try:
            enabled = self.query_one("#switch_options_swings_enabled", Switch).value
            options_swings["enabled"] = enabled
        except Exception:
            pass
            
        # Entry order types
        order_types = []
        available_order_types = ["market", "limit"]
        for order_type in available_order_types:
            try:
                checkbox = self.query_one(f"#checkbox_order_type_{order_type}", Checkbox)
                if checkbox.value:
                    order_types.append(order_type)
            except Exception:
                pass
                
        options_swings["entry_order_types"] = order_types
        
        # TP-SL types
        tp_sl_types = []
        available_tp_sl_types = ["STOCK_PRICE", "PREMIUM_PCT", "STOCK_PRICE_PCT"]
        for tp_sl_type in available_tp_sl_types:
            try:
                checkbox = self.query_one(f"#checkbox_tp_sl_{tp_sl_type}", Checkbox)
                if checkbox.value:
                    tp_sl_types.append(tp_sl_type)
            except Exception:
                pass
                
        options_swings["TP-SL_types"] = tp_sl_types
        
        # Take Profit settings
        try:
            multiple_tps = self.query_one("#switch_multiple_tps", Switch).value
            options_swings["Take_Profit"]["multiple_TPs"] = multiple_tps
        except Exception:
            pass
            
        # Play types
        play_types = []
        available_play_types = ["SIMPLE", "PRIMARY", "OCO", "OTO"]
        for play_type in available_play_types:
            try:
                checkbox = self.query_one(f"#checkbox_play_type_{play_type}", Checkbox)
                if checkbox.value:
                    play_types.append(play_type)
            except Exception:
                pass
                
        options_swings["play_types"] = play_types
        
        self.modified = True
        
    def update_monitoring_settings(self) -> None:
        """Update monitoring settings from form fields."""
        try:
            max_retries = int(self.query_one("#input_max_retries", Input).value)
            retry_delay = int(self.query_one("#input_retry_delay", Input).value)
            polling_interval = int(self.query_one("#input_polling_interval", Input).value)
            
            self.settings["monitoring"]["max_retries"] = max_retries
            self.settings["monitoring"]["retry_delay"] = retry_delay
            self.settings["monitoring"]["polling_interval"] = polling_interval
            
            self.modified = True
        except ValueError as e:
            self.notify(f"Please enter valid numbers for monitoring settings: {e}", severity="error")
        except Exception as e:
            self.notify(f"Error updating monitoring settings: {e}", severity="error")
            
    def update_orders_settings(self) -> None:
        """Update order settings from form fields."""
        try:
            # Bid price settings
            use_bid_price = self.query_one("#switch_use_bid_price", Switch).value
            entry_bid = self.query_one("#switch_entry_bid", Switch).value
            tp_bid = self.query_one("#switch_tp_bid", Switch).value
            sl_bid = self.query_one("#switch_sl_bid", Switch).value
            
            self.settings["orders"]["bid_price_settings"]["use_bid_price"] = use_bid_price
            self.settings["orders"]["bid_price_settings"]["entry"] = entry_bid
            self.settings["orders"]["bid_price_settings"]["take_profit"] = tp_bid
            self.settings["orders"]["bid_price_settings"]["stop_loss"] = sl_bid
            
            # Limit order settings
            timeout_enabled = self.query_one("#switch_timeout_enabled", Switch).value
            max_duration = int(self.query_one("#input_max_duration", Input).value)
            check_interval = int(self.query_one("#input_check_interval", Input).value)
            
            self.settings["orders"]["limit_order"]["timeout_enabled"] = timeout_enabled
            self.settings["orders"]["limit_order"]["max_duration_minutes"] = max_duration
            self.settings["orders"]["limit_order"]["check_interval_seconds"] = check_interval
            
            self.modified = True
        except ValueError as e:
            self.notify(f"Please enter valid numbers for order settings: {e}", severity="error")
        except Exception as e:
            self.notify(f"Error updating order settings: {e}", severity="error")
            
    def update_market_hours_settings(self) -> None:
        """Update market hours settings from form fields."""
        try:
            # Basic settings
            enabled = self.query_one("#switch_market_hours_enabled", Switch).value
            timezone = self.query_one("#input_timezone", Input).value
            
            self.settings["market_hours"]["enabled"] = enabled
            self.settings["market_hours"]["timezone"] = timezone
            
            # Regular hours
            regular_start = self.query_one("#input_regular_start", Input).value
            regular_end = self.query_one("#input_regular_end", Input).value
            
            self.settings["market_hours"]["regular_hours"]["start"] = regular_start
            self.settings["market_hours"]["regular_hours"]["end"] = regular_end
            
            # Extended hours
            extended_enabled = self.query_one("#switch_extended_hours_enabled", Switch).value
            pre_market_start = self.query_one("#input_pre_market_start", Input).value
            after_market_end = self.query_one("#input_after_market_end", Input).value
            
            self.settings["market_hours"]["extended_hours"]["enabled"] = extended_enabled
            self.settings["market_hours"]["extended_hours"]["pre_market_start"] = pre_market_start
            self.settings["market_hours"]["extended_hours"]["after_market_end"] = after_market_end
            
            self.modified = True
        except Exception as e:
            self.notify(f"Error updating market hours settings: {e}", severity="error")
            
    def update_auto_play_creator_settings(self) -> None:
        """Update auto play creator settings from form fields."""
        try:
            # Basic settings
            enabled = self.query_one("#switch_auto_play_enabled", Switch).value
            self.settings["auto_play_creator"]["enabled"] = enabled
            
            # Order types
            order_types = []
            available_order_types = ["market", "limit"]
            for order_type in available_order_types:
                try:
                    checkbox = self.query_one(f"#checkbox_apc_order_type_{order_type}", Checkbox)
                    if checkbox.value:
                        order_types.append(order_type)
                except Exception:
                    pass
                    
            self.settings["auto_play_creator"]["order_types"] = order_types
            
            # Trade types
            trade_types = []
            available_trade_types = ["CALL", "PUT", "MIX"]
            for trade_type in available_trade_types:
                try:
                    checkbox = self.query_one(f"#checkbox_trade_type_{trade_type}", Checkbox)
                    if checkbox.value:
                        trade_types.append(trade_type)
                except Exception:
                    pass
                    
            self.settings["auto_play_creator"]["trade_types"] = trade_types
            
            # Default values
            expiration_days = int(self.query_one("#input_expiration_days", Input).value)
            entry_buffer = float(self.query_one("#input_entry_buffer", Input).value)
            take_profit_pct = float(self.query_one("#input_take_profit_pct", Input).value)
            stop_loss_pct = float(self.query_one("#input_stop_loss_pct", Input).value)
            
            self.settings["auto_play_creator"]["expiration_days"] = expiration_days
            self.settings["auto_play_creator"]["entry_buffer"] = entry_buffer
            self.settings["auto_play_creator"]["take_profit_pct"] = take_profit_pct
            self.settings["auto_play_creator"]["stop_loss_pct"] = stop_loss_pct
            
            # Test symbols
            symbols_str = self.query_one("#input_test_symbols", Input).value
            symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]
            self.settings["auto_play_creator"]["test_symbols"] = symbols
            
            self.modified = True
        except ValueError as e:
            self.notify(f"Please enter valid numbers for auto play creator settings: {e}", severity="error")
        except Exception as e:
            self.notify(f"Error updating auto play creator settings: {e}", severity="error")
            
    def update_chart_viewer_settings(self) -> None:
        """Update chart viewer settings."""
        try:
            # Indicators settings
            indicators_enabled = self.query_one("#switch_indicators_enabled", Switch).value
            self.settings["chart_viewer"]["indicators"]["enabled"] = indicators_enabled
            
            # EMA settings
            ema_enabled = self.query_one("#switch_ema_enabled", Switch).value
            self.settings["chart_viewer"]["indicators"]["ema"]["enabled"] = ema_enabled
            
            ema_periods_str = self.query_one("#input_ema_periods", Input).value
            try:
                ema_periods = [int(p.strip()) for p in ema_periods_str.split(",") if p.strip()]
                self.settings["chart_viewer"]["indicators"]["ema"]["periods"] = ema_periods
            except ValueError:
                self.notify("Please enter valid EMA periods (comma-separated numbers)", severity="warning")
                
            # Display settings
            style = self.query_one("#input_chart_style", Input).value
            candle_up_color = self.query_one("#input_candle_up_color", Input).value
            candle_down_color = self.query_one("#input_candle_down_color", Input).value
            background_color = self.query_one("#input_background_color", Input).value
            grid = self.query_one("#switch_grid", Switch).value
            
            self.settings["chart_viewer"]["display"]["style"] = style
            self.settings["chart_viewer"]["display"]["candle_up_color"] = candle_up_color
            self.settings["chart_viewer"]["display"]["candle_down_color"] = candle_down_color
            self.settings["chart_viewer"]["display"]["background_color"] = background_color
            self.settings["chart_viewer"]["display"]["grid"] = grid
            
            self.modified = True
        except Exception as e:
            self.notify(f"Error updating chart viewer settings: {e}", severity="error")
            
    def display_section(self, section: str) -> None:
        """Display a specific section of settings."""
        self.current_section = section
        
        # Clear the current settings container
        settings_container = self.query_one("#settings_container", ScrollableContainer)
        settings_container.remove_children()
        
        # Add the section title
        settings_container.mount(Static(f"# {self.sections[section]}", classes="section_title"))
        
        # Display the appropriate form based on the section
        if section == "alpaca":
            self.display_alpaca_settings(settings_container)
        elif section == "market_data":
            self.display_market_data_settings(settings_container)
        elif section == "options_swings":
            self.display_options_swings_settings(settings_container)
        elif section == "monitoring":
            self.display_monitoring_settings(settings_container)
        elif section == "orders":
            self.display_orders_settings(settings_container)
        elif section == "market_hours":
            self.display_market_hours_settings(settings_container)
        elif section == "auto_play_creator":
            self.display_auto_play_creator_settings(settings_container)
        elif section == "chart_viewer":
            self.display_chart_viewer_settings(settings_container)
        
    def display_alpaca_settings(self, container: ScrollableContainer) -> None:
        """Display Alpaca API settings."""
        # Get the Alpaca settings
        alpaca_settings = self.settings.get("alpaca", {})
        accounts = alpaca_settings.get("accounts", {})
        
        # Add account widgets
        for account_name, account_data in accounts.items():
            account_container = Container(id=f"account_{account_name}")
            container.mount(account_container)
            
            # Create widgets for this account
            account_container.mount(Static(f"Account: {account_name}", classes="subsection_title"))
            account_container.mount(Horizontal(
                Label("Nickname:"),
                Input(value=account_data.get("nickname", ""), id=f"input_nickname_{account_name}"),
                id=f"nickname_row_{account_name}"
            ))
            account_container.mount(Horizontal(
                Label("API Key:"),
                Input(value=account_data.get("api_key", ""), id=f"input_api_key_{account_name}"),
                id=f"api_key_row_{account_name}"
            ))
            account_container.mount(Horizontal(
                Label("Secret Key:"),
                Input(value=account_data.get("secret_key", ""), 
                      password=True, id=f"input_secret_key_{account_name}"),
                id=f"secret_key_row_{account_name}"
            ))
            account_container.mount(Horizontal(
                Label("Base URL:"),
                Input(value=account_data.get("base_url", ""), id=f"input_base_url_{account_name}"),
                id=f"base_url_row_{account_name}"
            ))
            account_container.mount(Horizontal(
                Label("Enabled:"),
                Switch(value=account_data.get("enabled", False), id=f"switch_enabled_{account_name}"),
                id=f"enabled_row_{account_name}"
            ))
            
        # Add active account selector
        active_account = alpaca_settings.get("active_account", "")
        account_options = [(name, name) for name in accounts.keys()]
        
        active_account_container = Container(id="active_account_container")
        container.mount(active_account_container)
        
        active_account_container.mount(Static("Active Account", classes="subsection_title"))
        active_account_container.mount(Horizontal(
            Label("Active Account:"),
            Select(
                account_options,
                value=active_account,
                id="select_active_account"
            ),
            id="active_account_row"
        ))
        
    def display_market_hours_settings(self, container: ScrollableContainer) -> None:
        """Display market hours settings."""
        market_hours = self.settings.get("market_hours", {})
        
        basic_container = Container(id="basic_market_hours")
        container.mount(basic_container)  # Mount to parent first
        
        basic_container.mount(Static("Market Hours Settings", classes="subsection_title"))
        
        basic_container.mount(Horizontal(
            Label("Enabled:"),
            Switch(value=market_hours.get("enabled", True), id="switch_market_hours_enabled"),
            id="market_hours_enabled_row"
        ))
        
        basic_container.mount(Horizontal(
            Label("Timezone:"),
            Input(value=market_hours.get("timezone", "America/New_York"), 
                 id="input_timezone"),
            id="timezone_row"
        ))
        
        # Regular hours
        regular_hours = market_hours.get("regular_hours", {})
        
        regular_container = Container(id="regular_hours_container")
        container.mount(regular_container)  # Mount to parent first
        
        regular_container.mount(Static("Regular Market Hours", classes="subsection_title"))
        
        regular_container.mount(Horizontal(
            Label("Start Time:"),
            Input(value=regular_hours.get("start", "09:30"), id="input_regular_start"),
            id="regular_start_row"
        ))
        
        regular_container.mount(Horizontal(
            Label("End Time:"),
            Input(value=regular_hours.get("end", "16:00"), id="input_regular_end"),
            id="regular_end_row"
        ))
        
        # Extended hours
        extended_hours = market_hours.get("extended_hours", {})
        
        extended_container = Container(id="extended_hours_container")
        container.mount(extended_container)  # Mount to parent first
        
        extended_container.mount(Static("Extended Market Hours", classes="subsection_title"))
        
        extended_container.mount(Horizontal(
            Label("Enabled:"),
            Switch(value=extended_hours.get("enabled", False), 
                  id="switch_extended_hours_enabled"),
            id="extended_hours_enabled_row"
        ))
        
        extended_container.mount(Horizontal(
            Label("Pre-Market Start:"),
            Input(value=extended_hours.get("pre_market_start", "04:00"), 
                 id="input_pre_market_start"),
            id="pre_market_start_row"
        ))
        
        extended_container.mount(Horizontal(
            Label("After-Market End:"),
            Input(value=extended_hours.get("after_market_end", "20:00"), 
                 id="input_after_market_end"),
            id="after_market_end_row"
        ))

    def display_options_swings_settings(self, container: ScrollableContainer) -> None:
        """Display options swings strategy settings."""
        options_swings = self.settings.get("options_swings", {})
        
        # Basic settings
        basic_container = Container(id="basic_options_swings")
        container.mount(basic_container)  # Mount to parent first
        
        basic_container.mount(Static("Options Swings Settings", classes="subsection_title"))
        basic_container.mount(Horizontal(
            Label("Enabled:"),
            Switch(value=options_swings.get("enabled", True), id="switch_options_swings_enabled"),
            id="options_swings_enabled_row"
        ))
        
        # Entry order types
        order_types_container = Container(id="order_types_container")
        container.mount(order_types_container)  # Mount to parent first
        
        order_types_container.mount(Static("Entry Order Types:", classes="field_label"))
        
        entry_order_types = options_swings.get("entry_order_types", [])
        available_order_types = ["market", "limit"]
        
        for order_type in available_order_types:
            order_types_container.mount(Horizontal(
                Checkbox(order_type, value=order_type in entry_order_types, 
                        id=f"checkbox_order_type_{order_type}"),
                id=f"order_type_row_{order_type}"
            ))
        
        # TP-SL types
        tp_sl_container = Container(id="tp_sl_container")
        container.mount(tp_sl_container)  # Mount to parent first
        
        tp_sl_container.mount(Static("Take Profit / Stop Loss Types:", classes="field_label"))
        
        tp_sl_types = options_swings.get("TP-SL_types", [])
        available_tp_sl_types = ["STOCK_PRICE", "PREMIUM_PCT", "STOCK_PRICE_PCT"]
        
        for tp_sl_type in available_tp_sl_types:
            tp_sl_container.mount(Horizontal(
                Checkbox(tp_sl_type, value=tp_sl_type in tp_sl_types, 
                        id=f"checkbox_tp_sl_{tp_sl_type}"),
                id=f"tp_sl_row_{tp_sl_type}"
            ))
        
        # Take Profit settings
        tp_settings = options_swings.get("Take_Profit", {})
        
        tp_container = Container(id="tp_container")
        container.mount(tp_container)  # Mount to parent first
        
        tp_container.mount(Static("Take Profit Settings:", classes="field_label"))
        tp_container.mount(Horizontal(
            Label("Multiple TPs:"),
            Switch(value=tp_settings.get("multiple_TPs", False), id="switch_multiple_tps"),
            id="multiple_tps_row"
        ))
        
        # Play types
        play_types_container = Container(id="play_types_container")
        container.mount(play_types_container)  # Mount to parent first
        
        play_types_container.mount(Static("Play Types:", classes="field_label"))
        
        play_types = options_swings.get("play_types", [])
        available_play_types = ["SIMPLE", "PRIMARY", "OCO", "OTO"]
        
        for play_type in available_play_types:
            play_types_container.mount(Horizontal(
                Checkbox(play_type, value=play_type in play_types, 
                        id=f"checkbox_play_type_{play_type}"),
                id=f"play_type_row_{play_type}"
            ))

    def display_monitoring_settings(self, container: ScrollableContainer) -> None:
        """Display monitoring settings."""
        monitoring = self.settings.get("monitoring", {})
        
        monitoring_container = Container(id="monitoring_container")
        container.mount(monitoring_container)  # Mount to parent first
        
        monitoring_container.mount(Static("Monitoring Settings", classes="subsection_title"))
        
        monitoring_container.mount(Horizontal(
            Label("Max Retries:"),
            Input(value=str(monitoring.get("max_retries", 3)), id="input_max_retries"),
            id="max_retries_row"
        ))
        
        monitoring_container.mount(Horizontal(
            Label("Retry Delay (seconds):"),
            Input(value=str(monitoring.get("retry_delay", 2)), id="input_retry_delay"),
            id="retry_delay_row"
        ))
        
        monitoring_container.mount(Horizontal(
            Label("Polling Interval (seconds):"),
            Input(value=str(monitoring.get("polling_interval", 30)), id="input_polling_interval"),
            id="polling_interval_row"
        ))

    def display_orders_settings(self, container: ScrollableContainer) -> None:
        """Display order settings."""
        orders = self.settings.get("orders", {})
        
        # Bid price settings
        bid_price_settings = orders.get("bid_price_settings", {})
        
        bid_price_container = Container(id="bid_price_container")
        container.mount(bid_price_container)  # Mount to parent first
        
        bid_price_container.mount(Static("Bid Price Settings", classes="subsection_title"))
        
        bid_price_container.mount(Horizontal(
            Label("Use Bid Price:"),
            Switch(value=bid_price_settings.get("use_bid_price", True), 
                  id="switch_use_bid_price"),
            id="use_bid_price_row"
        ))
        
        bid_price_container.mount(Horizontal(
            Label("Entry:"),
            Switch(value=bid_price_settings.get("entry", True), id="switch_entry_bid"),
            id="entry_bid_row"
        ))
        
        bid_price_container.mount(Horizontal(
            Label("Take Profit:"),
            Switch(value=bid_price_settings.get("take_profit", True), id="switch_tp_bid"),
            id="tp_bid_row"
        ))
        
        bid_price_container.mount(Horizontal(
            Label("Stop Loss:"),
            Switch(value=bid_price_settings.get("stop_loss", True), id="switch_sl_bid"),
            id="sl_bid_row"
        ))
        
        # Limit order settings
        limit_order = orders.get("limit_order", {})
        
        limit_order_container = Container(id="limit_order_container")
        container.mount(limit_order_container)  # Mount to parent first
        
        limit_order_container.mount(Static("Limit Order Settings", classes="subsection_title"))
        
        limit_order_container.mount(Horizontal(
            Label("Timeout Enabled:"),
            Switch(value=limit_order.get("timeout_enabled", False), 
                  id="switch_timeout_enabled"),
            id="timeout_enabled_row"
        ))
        
        limit_order_container.mount(Horizontal(
            Label("Max Duration (minutes):"),
            Input(value=str(limit_order.get("max_duration_minutes", 5)), 
                 id="input_max_duration"),
            id="max_duration_row"
        ))
        
        limit_order_container.mount(Horizontal(
            Label("Check Interval (seconds):"),
            Input(value=str(limit_order.get("check_interval_seconds", 30)), 
                 id="input_check_interval"),
            id="check_interval_row"
        ))

    def display_auto_play_creator_settings(self, container: ScrollableContainer) -> None:
        """Display auto play creator settings."""
        auto_play = self.settings.get("auto_play_creator", {})
        
        basic_container = Container(id="basic_auto_play")
        container.mount(basic_container)  # Mount to parent first
        
        basic_container.mount(Static("Auto Play Creator Settings", classes="subsection_title"))
        basic_container.mount(Horizontal(
            Label("Enabled:"),
            Switch(value=auto_play.get("enabled", True), id="switch_auto_play_enabled"),
            id="auto_play_enabled_row"
        ))
        
        # Order types
        order_types = auto_play.get("order_types", [])
        available_order_types = ["market", "limit"]
        
        order_types_container = Container(id="apc_order_types_container")
        container.mount(order_types_container)  # Mount to parent first
        
        order_types_container.mount(Static("Order Types:", classes="field_label"))
        
        for order_type in available_order_types:
            order_types_container.mount(Horizontal(
                Checkbox(order_type, value=order_type in order_types, 
                        id=f"checkbox_apc_order_type_{order_type}"),
                id=f"apc_order_type_row_{order_type}"
            ))
        
        # Trade types
        trade_types = auto_play.get("trade_types", [])
        available_trade_types = ["CALL", "PUT", "MIX"]
        
        trade_types_container = Container(id="trade_types_container")
        container.mount(trade_types_container)  # Mount to parent first
        
        trade_types_container.mount(Static("Trade Types:", classes="field_label"))
        
        for trade_type in available_trade_types:
            trade_types_container.mount(Horizontal(
                Checkbox(trade_type, value=trade_type in trade_types, 
                        id=f"checkbox_trade_type_{trade_type}"),
                id=f"trade_type_row_{trade_type}"
            ))
        
        # Basic settings
        defaults_container = Container(id="apc_defaults_container")
        container.mount(defaults_container)  # Mount to parent first
        
        defaults_container.mount(Static("Default Values:", classes="field_label"))
        
        defaults_container.mount(Horizontal(
            Label("Expiration Days:"),
            Input(value=str(auto_play.get("expiration_days", 7)), 
                 id="input_expiration_days"),
            id="expiration_days_row"
        ))
        
        defaults_container.mount(Horizontal(
            Label("Entry Buffer:"),
            Input(value=str(auto_play.get("entry_buffer", 0.5)), 
                 id="input_entry_buffer"),
            id="entry_buffer_row"
        ))
        
        defaults_container.mount(Horizontal(
            Label("Take Profit %:"),
            Input(value=str(auto_play.get("take_profit_pct", 1.5)), 
                 id="input_take_profit_pct"),
            id="take_profit_pct_row"
        ))
        
        defaults_container.mount(Horizontal(
            Label("Stop Loss %:"),
            Input(value=str(auto_play.get("stop_loss_pct", 0.75)), 
                 id="input_stop_loss_pct"),
            id="stop_loss_pct_row"
        ))
        
        # Test symbols
        symbols_container = Container(id="test_symbols_container")
        container.mount(symbols_container)  # Mount to parent first
        
        symbols_container.mount(Static("Test Symbols:", classes="field_label"))
        
        symbols_input = Input(
            value=", ".join(auto_play.get("test_symbols", [])),
            id="input_test_symbols"
        )
        symbols_container.mount(symbols_input)

    def display_chart_viewer_settings(self, container: ScrollableContainer) -> None:
        """Display chart viewer settings."""
        chart_viewer = self.settings.get("chart_viewer", {})
        indicators = chart_viewer.get("indicators", {})
        
        # Indicators settings
        indicators_container = Container(id="chart_indicators_container")
        container.mount(indicators_container)  # Mount to parent first
        
        indicators_container.mount(Static("Chart Indicators", classes="subsection_title"))
        indicators_container.mount(Horizontal(
            Label("Enabled:"),
            Switch(value=indicators.get("enabled", True), id="switch_indicators_enabled"),
            id="indicators_enabled_row"
        ))
        
        # EMA settings
        ema = indicators.get("ema", {})
        
        ema_container = Container(id="ema_container")
        container.mount(ema_container)  # Mount to parent first
        
        ema_container.mount(Static("EMA Settings", classes="subsection_title"))
        ema_container.mount(Horizontal(
            Label("Enabled:"),
            Switch(value=ema.get("enabled", True), id="switch_ema_enabled"),
            id="ema_enabled_row"
        ))
        
        ema_periods_input = Input(
            value=", ".join(str(p) for p in ema.get("periods", [])),
            id="input_ema_periods"
        )
        ema_container.mount(Horizontal(
            Label("Periods:"),
            ema_periods_input,
            id="ema_periods_row"
        ))
        
        # Display settings
        display = chart_viewer.get("display", {})
        
        display_container = Container(id="chart_display_container")
        container.mount(display_container)  # Mount to parent first
        
        display_container.mount(Static("Display Settings", classes="subsection_title"))
        display_container.mount(Horizontal(
            Label("Style:"),
            Input(value=display.get("style", "charles"), id="input_chart_style"),
            id="chart_style_row"
        ))
        
        display_container.mount(Horizontal(
            Label("Candle Up Color:"),
            Input(value=display.get("candle_up_color", "green"), 
                 id="input_candle_up_color"),
            id="candle_up_color_row"
        ))
        
        display_container.mount(Horizontal(
            Label("Candle Down Color:"),
            Input(value=display.get("candle_down_color", "red"), 
                 id="input_candle_down_color"),
            id="candle_down_color_row"
        ))
        
        display_container.mount(Horizontal(
            Label("Background Color:"),
            Input(value=display.get("background_color", "white"), 
                 id="input_background_color"),
            id="background_color_row"
        ))
        
        display_container.mount(Horizontal(
            Label("Show Grid:"),
            Switch(value=display.get("grid", True), id="switch_grid"),
            id="grid_row"
        ))

class GoldflipperTUI(App):
    CSS = """
    /* Original styles */
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
        opacity: 1;
        transition: opacity 0.5s linear;
    }
    
    #welcome.faded {
        opacity: 0;
    }
    
    #header_container {
        width: 100%;
        height: auto;
        align: center middle;
        margin: 1 1 2 1;
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
    
    /* Center confirmation dialog text */
    #confirmation_message, #confirmation_instructions {
        text-align: center;
        width: 100%;
    }
    
    /* Configuration screen styles */
    #config_title {
        content-align: center middle;
        background: $accent;
        color: $text;
        padding: 1 1;
        text-style: bold;
        margin-bottom: 1;
    }
    
    #title_container {
        width: 100%;
        margin-bottom: 1;
    }
    
    #config_layout {
        width: 100%;
        height: auto;
    }
    
    #nav_sidebar {
        width: 25%;
        height: auto;
        margin-right: 1;
    }
    
    #settings_container {
        width: 75%;
        height: auto;
        padding: 1 1;
        border: solid $accent;
    }
    
    #action_buttons {
        width: 100%;
        height: auto;
        margin-top: 1;
        align: center middle;
    }
    
    .section_title {
        background: $accent-darken-1;
        color: $text;
        padding: 1 1;
        text-style: bold;
        margin-bottom: 1;
    }
    
    .subsection_title {
        background: $accent-darken-2;
        color: $text;
        padding: 0 1;
        margin-top: 1;
        margin-bottom: 1;
    }
    
    .field_label {
        color: $text;
        padding: 0 1;
    }
    
    #config_buttons {
        layout: vertical;
        background: $surface;
        height: auto;
        margin: 1 2;
        padding: 1 2;
        width: 100%;
        align: center middle;
    }
    
    #config_container {
        width: 100%;
        height: 100%;
        align: center middle;
        background: $surface;
        border: none;
    }
    """

    SCREENS = {
        "welcome": WelcomeScreen,
        "config_choice": ConfigChoiceScreen,
        "graphical_config": GraphicalConfigScreen,
    }

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def on_mount(self) -> None:
        self.push_screen("welcome")

if __name__ == "__main__":
    app = GoldflipperTUI()
    app.run()