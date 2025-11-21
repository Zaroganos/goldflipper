from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Button, Static, Select
from textual.screen import Screen
import subprocess
import sys
import os
import time
from pathlib import Path
from goldflipper.config.config import config, settings_just_created, reset_settings_created_flag
import yaml
import asyncio  # Added for asyncio.to_thread

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
                "Welcome to Goldflipper! Your settings file has been created. Please configure your settings before launching the trading system.",
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
            win32serviceutil.QueryServiceStatus("GoldflipperService")
            service_installed = True
        except Exception:
            service_installed = False

        if service_installed:
            message = (
                "You are about to STOP and UNINSTALL the Goldflipper Service.\n"
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
                    "python -m goldflipper.run --mode install; Start-Sleep -Seconds 2; net start GoldflipperService"
                )
            else:
                final_command = "net stop GoldflipperService; python -m goldflipper.run --mode remove"
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
        Launch the configuration tool to edit settings.yaml.
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
            logging_dir = os.path.join(current_dir, "trade_logging")
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
                os.path.join(tools_dir, "play_csv_ingestion_tool.py"),
                file_path
            ]
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:  # Unix-like systems
            cmd = [
                "gnome-terminal", "--", "python3",
                os.path.join(tools_dir, "play_csv_ingestion_tool.py"),
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
        opacity: 1;
        transition: opacity 0.5s linear;
    }
    
    #welcome.faded {
        opacity: 0;
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
    """

    def on_mount(self) -> None:
        self.push_screen(WelcomeScreen())

if __name__ == "__main__":
    app = GoldflipperTUI()
    app.run()