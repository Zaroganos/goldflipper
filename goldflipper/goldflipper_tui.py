#!/usr/bin/env python
if __name__ == '__main__' and __package__ is None:
    import sys, os
    # Insert the parent directory (the project root) into sys.path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "goldflipper"

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Button, Static, Select
from textual.screen import Screen
import subprocess
import sys
import os
from pathlib import Path
from .config.config import config
import yaml
import asyncio  # Added for asyncio.to_thread
# Import our helper that resolves resource paths correctly
from goldflipper.utils.resource import get_resource_path

def get_resource_path(relative_path):
    """
    Get absolute path to a bundled resource.
    Works for both development and frozen (PyInstaller) environments.
    """
    if getattr(sys, "frozen", False):
        # In PyInstaller one-file (or one-folder) mode, resources are in sys._MEIPASS.
        base_path = sys._MEIPASS
    else:
        # Otherwise, use the directory of the current file.
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

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
        
        # Determine active account to show its nickname as the prompt if available.
        active_account = config.get('alpaca', 'active_account')
        active_prompt = "Select Trading Account"
        if active_account and active_account in config.get('alpaca', 'accounts'):
            account_info = config.get('alpaca', 'accounts')[active_account]
            if account_info.get('enabled', False):
                active_prompt = account_info.get('nickname', active_account.replace('_', ' ').title())
        
        yield Container(
            Horizontal(
                Static(" Welcome to Goldflipper ", id="welcome"),
                Select(
                    [(acc.get('nickname', name.replace('_', ' ').title()), name)
                     for name, acc in config.get('alpaca', 'accounts').items()
                     if acc.get('enabled', False)],
                    prompt=active_prompt,
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

    async def update_connection_status(self) -> None:
        """
        Check the connection status using test_alpaca_connection,
        then update the account selector by replacing it with a new instance.
        This new instance will show the active account connection status.
        """
        import asyncio, os, yaml
        from .tools.get_alpaca_info import test_alpaca_connection

        # Try to import Option (with fallback).
        try:
            from textual.widgets.select import Option
        except ImportError:
            from collections import namedtuple
            Option = namedtuple("Option", ["label", "value"])

        # Force a reset of the Alpaca client.
        try:
            from .alpaca_client import reset_client
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
        from .utils import trading_system_status
        is_running = trading_system_status.is_trading_system_running()
        status_text = "[green]Trading System: Running[/green]" if is_running else "[red]Trading System: Not Running[/red]"
        widget.update(f" {status_text} ")
        widget.remove_class("faded")
        self.set_interval(5, self.refresh_status_in_welcome)

    def refresh_status_in_welcome(self) -> None:
        from .utils import trading_system_status
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
            from .alpaca_client import reset_client
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
        elif event.button.id == "market_data_compare":
            self.run_market_data_compare()
        elif event.button.id == "manage_service":
            self.run_manage_service()

    def run_manage_service(self) -> None:
        """
        Launch the service management actions (install/remove/update) in an elevated PowerShell window.
        This function displays a confirmation screen; upon confirmation it uses sys.executable
        to invoke the run_goldflipper.py module with the relevant mode.
        """
        try:
            import sys, os, subprocess
            # Determine the intended mode; here we assume mode is predetermined.
            # In practice you may want to provide a proper UI selection.
            mode = "install"  # Change this to "remove" as needed.
            if mode == "remove":
                message = (
                    "You are about to STOP and UNINSTALL the GoldFlipper Service.\n"
                    "This will stop the running service and uninstall it.\n"
                    "This requires administrative privileges and will launch an elevated process.\n"
                    "Note: Changes made will not take effect until you reboot.\n"
                    "Do you want to proceed? (Y/N)"
                )
            else:
                message = (
                    "You are about to INSTALL the GoldFlipper Service and automatically start it.\n"
                    "This requires administrative privileges and will launch an elevated process.\n"
                    "Note: Changes made will not take effect until you reboot.\n"
                    "Do you want to proceed? (Y/N)"
                )

            def perform_action():
                if mode == "install":
                    final_command = f'"{sys.executable}" -m goldflipper.run --mode install; Start-Sleep -Seconds 2; net start GoldFlipperService'
                else:
                    final_command = f'net stop GoldFlipperService; "{sys.executable}" -m goldflipper.run --mode remove'
                ps_command = f"Start-Process powershell -ArgumentList '-NoProfile -Command \"{final_command}\"' -Verb RunAs"
                subprocess.Popen(["powershell", "-Command", ps_command])
                self.notify(f"{'Uninstallation' if mode=='remove' else 'Installation'} initiated. Changes will require a reboot to apply.")

            self.app.push_screen(ConfirmationScreen(message, perform_action))
        except Exception as e:
            self.notify(f"Error managing service: {str(e)}", severity="error")

    def run_option_data_fetcher(self) -> None:
        """
        Launch the Option Data Fetcher tool.
        """
        try:
            import sys, os, subprocess
            cmd = [sys.executable, "--tool", "option_data_fetcher"]
            if os.name == "nt":
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(cmd)
        except Exception as e:
            self.notify(f"Error launching Option Data Fetcher: {str(e)}", severity="error")

    def run_play_creation_tool(self) -> None:
        """
        Launch the Play Creation Tool.
        """
        try:
            import sys, os, subprocess
            cmd = [sys.executable, "--tool", "play_creation"]
            if os.name == "nt":
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(cmd)
        except Exception as e:
            self.notify(f"Error launching Play Creation Tool: {str(e)}", severity="error")

    def run_trading_monitor(self) -> None:
        """
        Launch the trading system.
        In frozen mode, this launches the bundled executable (run_goldflipper.py)
        with the '--interface trading' argument so that it initiates the trading system
        rather than launching the TUI again.
        """
        try:
            import sys, os, subprocess
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "--interface", "trading"]
                if os.name == 'nt':
                    subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen(cmd)
            else:
                cmd = [sys.executable, "-m", "goldflipper.run", "--interface", "trading"]
                if os.name == 'nt':
                    cmd = ["cmd", "/k"] + cmd
                    subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen(cmd)
        except Exception as e:
            self.notify(f"Error launching trading monitor: {str(e)}", severity="error")

    def run_view_plays(self) -> None:
        """
        Launch the tool to View / Edit Current Plays.
        """
        try:
            import sys, os, subprocess
            cmd = [sys.executable, "--tool", "view_plays"]
            if os.name == "nt":
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(cmd)
        except Exception as e:
            self.notify(f"Error launching View Plays: {str(e)}", severity="error")

    def run_system_status(self) -> None:
        """
        Launch a tool to show system status.
        (If you do not have an external system_status tool implemented,
         update your dispatch logic accordingly.)
        """
        try:
            import sys, os, subprocess
            cmd = [sys.executable, "--tool", "system_status"]
            if os.name == "nt":
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(cmd)
        except Exception as e:
            self.notify(f"Error launching System Status: {str(e)}", severity="error")

    def run_configuration(self) -> None:
        """
        Launch the Configuration by opening the settings file in a text editor.
        """
        try:
            import sys, os, subprocess
            from goldflipper.utils.resource import get_resource_path
            config_dir = get_resource_path(os.path.join("goldflipper", "config"))
            config_file = os.path.join(config_dir, "settings.yaml")
            if os.name == "nt":
                subprocess.Popen(["notepad.exe", config_file])
            else:
                subprocess.Popen(["nano", config_file])
        except Exception as e:
            self.notify(f"Error launching Configuration: {str(e)}", severity="error")

    def run_auto_play_creator(self) -> None:
        """
        Launch the Auto Play Creator tool.
        """
        try:
            import sys, os, subprocess
            cmd = [sys.executable, "--tool", "auto_play_creator"]
            if os.name == "nt":
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(cmd)
        except Exception as e:
            self.notify(f"Error launching Auto Play Creator: {str(e)}", severity="error")

    def run_chart_viewer(self) -> None:
        """
        Launch the Chart Viewer tool.
        """
        try:
            import sys, os, subprocess
            cmd = [sys.executable, "--tool", "chart_viewer"]
            if os.name == "nt":
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(cmd)
        except Exception as e:
            self.notify(f"Error launching Chart Viewer: {str(e)}", severity="error")

    def run_get_alpaca_info(self) -> None:
        """
        Launch the Get Alpaca Info tool.
        """
        try:
            import sys, os, subprocess
            cmd = [sys.executable, "--tool", "get_alpaca_info"]
            if os.name == "nt":
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(cmd)
        except Exception as e:
            self.notify(f"Error launching Get Alpaca Info: {str(e)}", severity="error")

    def run_trade_logger(self) -> None:
        """
        Launch the Trade Logger tool.
        """
        try:
            import sys, os, subprocess
            cmd = [sys.executable, "--tool", "trade_logger"]
            if os.name == "nt":
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(cmd)
        except Exception as e:
            self.notify(f"Error launching Trade Logger: {str(e)}", severity="error")

    def run_market_data_compare(self) -> None:
        """
        Launch the Market Data Compare tool.
        """
        try:
            import sys, os, subprocess
            cmd = [sys.executable, "--tool", "market_data_compare"]
            if os.name == "nt":
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(cmd)
        except Exception as e:
            self.notify(f"Error launching Market Data Compare: {str(e)}", severity="error")

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