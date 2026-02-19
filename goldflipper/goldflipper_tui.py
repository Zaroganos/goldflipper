import asyncio  # Added for asyncio.to_thread
import importlib
import os
import subprocess
import sys
import threading
import time
from typing import Any, cast

import yaml
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Select, Static

from goldflipper.config.config import config, reset_settings_created_flag, settings_just_created

# Import Nuitka-aware utilities from exe_utils
from goldflipper.utils.exe_utils import get_settings_path, is_frozen


def get_exe_path() -> str:
    """
    Get the path to the actual executable.

    CRITICAL: In Nuitka onefile mode, sys.executable points to python.exe
    inside the temp extraction directory, NOT to the original exe!
    Use sys.argv[0] which contains the actual exe path.
    """
    exe_path = sys.argv[0]
    if not os.path.isabs(exe_path):
        exe_path = os.path.abspath(exe_path)
    return exe_path


def run_tool_in_thread(module_name: str, entry_func: str = "main") -> None:
    """
    Run a tool module in a separate thread (for GUI tools that need their own event loop).

    Args:
        module_name: Full module path (e.g., "goldflipper.tools.play_creator_gui")
        entry_func: Function to call in the module (default: "main")
    """

    def _run():
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, entry_func):
                getattr(module, entry_func)()
            elif hasattr(module, "run"):
                module.run()
            else:
                # For modules that run on import (some GUI tools)
                pass
        except Exception as e:
            import logging

            logging.error(f"Error running tool {module_name}: {e}")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


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
        # Use exe-aware path for settings
        settings_path = str(get_settings_path())

        # Set button variants based on whether settings were just created
        launch_variant = "primary" if settings_just_created else "success"
        config_variant = "success" if settings_just_created else "primary"

        # Debug print to confirm path and existence
        print(f"\n\nDEBUG: Settings path (exe-aware): {settings_path}")
        print(f"DEBUG: Settings exists: {os.path.exists(settings_path)}")
        print(f"DEBUG: Settings just created: {settings_just_created}")
        print(f"DEBUG: is_frozen: {is_frozen()}\n\n")

        # Determine active account to show its nickname as the prompt if available.
        active_prompt = "Select Trading Account"
        try:
            active_account = config.get("alpaca", "active_account")
            if active_account and active_account in config.get("alpaca", "accounts", {}):
                account_info = config.get("alpaca", "accounts")[active_account]
                if account_info.get("enabled", False):
                    active_prompt = account_info.get("nickname", active_account.replace("_", " ").title())

            account_options = [
                (acc.get("nickname", name.replace("_", " ").title()), name)
                for name, acc in config.get("alpaca", "accounts", {}).items()
                if acc.get("enabled", False)
            ]
        except Exception:
            # If config can't be loaded, use empty account list
            account_options = []

        yield Container(
            Horizontal(
                Static(" Welcome to Goldflipper ", id="welcome"),
                Select(account_options if account_options else [("No Accounts Available", "none")], prompt=active_prompt, id="account_selector"),
                id="header_container",
            ),
            Horizontal(
                Container(
                    Button("Play Creator GUI", variant="success", id="play_creator_gui"),
                    Button("Create New Play", variant="primary", id="create_play"),
                    Button("Fetch Option Data", variant="primary", id="option_data_fetcher"),
                    Button("Auto Play Creator", variant="primary", id="auto_play_creator"),
                    # Button("Market Data Compare", variant="primary", id="market_data_compare"),  # Temporarily commented out
                    Button("Upload Template", variant="primary", id="upload_template"),
                    classes="button-column",
                ),
                Container(
                    Button("Launch Trading System", variant=launch_variant, id="start_monitor"),
                    Button("View / Edit Plays", variant="primary", id="view_plays"),
                    Button("Trade Logger", variant="primary", id="trade_logger"),
                    Button("Open Chart", variant="primary", id="open_chart"),
                    classes="button-column",
                ),
                Container(
                    Button("System Status", variant="primary", id="system_status"),
                    Button("Settings", variant=config_variant, id="configuration"),
                    Button("Get Alpaca Info", variant="primary", id="get_alpaca_info"),
                    Button("Manage Service", variant="warning", id="manage_service"),
                    classes="button-column",
                ),
                id="button_container",
            ),
            classes="container",
        )
        yield Footer()

    async def on_mount(self) -> None:
        # Transition the welcome text after 2 seconds
        self.set_timer(2, self.transition_to_status)
        # Update the connection status (and update periodically every 60 seconds)
        await self.update_connection_status()
        self.set_interval(60, lambda: self.call_later(self.update_connection_status))

        # Check if settings were just created using the global flag
        if settings_just_created:
            self.notify(
                "Welcome to Goldflipper! Your settings file has been created. Please configure your settings before launching the trading system.",
                title="New Configuration Created",
                timeout=10,
                severity="information",
            )

        # Schedule update check after a short delay so it never competes with startup
        self.set_timer(6, self._check_for_updates)

    async def _check_for_updates(self) -> None:
        """Background update check — reads settings, hits version.json, notifies if newer."""
        import yaml

        from goldflipper.utils.exe_utils import get_settings_path
        from goldflipper.utils.updater import check_for_update

        try:
            settings_path = get_settings_path()
            with open(settings_path, encoding="utf-8") as f:
                settings = yaml.safe_load(f) or {}
            uc = settings.get("update_check", {})
            url = str(uc.get("url", "")).strip()
            timeout = float(uc.get("timeout_seconds", 5))
        except Exception:
            return  # Can't read settings — fail silently

        if not url:
            return  # Not configured yet

        info = await asyncio.to_thread(check_for_update, url, timeout)

        if info and info.is_newer:
            lines = [f"Version {info.latest_version} is available (you have {info.current_version})."]
            if info.notes:
                lines.append(info.notes)
            if info.download_url:
                lines.append(f"Download: {info.download_url}")
            self.notify(
                "\n".join(lines),
                title="Update Available",
                timeout=30,
                severity="warning",
            )

    async def update_connection_status(self) -> None:
        """
        Check the connection status using test_alpaca_connection,
        then update the account selector by replacing it with a new instance.
        This new instance will show the active account connection status.
        """
        from goldflipper.tools.get_alpaca_info import test_alpaca_connection

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

        active_account_config = config.get("alpaca", "active_account")

        # Use exe-aware settings path
        settings_path = str(get_settings_path())
        try:
            with open(settings_path) as file:
                file_config = yaml.safe_load(file)
            _ = file_config.get("alpaca", {}).get("active_account", "unknown")
        except Exception as e:
            self.notify(f"Error reading settings file: {e}")

        try:
            _ = config.get("alpaca", "accounts")[active_account_config]
        except Exception:
            return

        # Run the connection test in a background thread.
        connection_status, _ = await asyncio.to_thread(test_alpaca_connection)

        # Build the options list with updated connection status.
        accounts = config.get("alpaca", "accounts")
        new_options: list[tuple[str, str]] = []
        for name, acc in accounts.items():
            account_nickname = acc.get("nickname", name.replace("_", " ").title())
            if name == active_account_config:
                if connection_status:
                    display_label = f"[green]Connected:[/green] {account_nickname}"
                else:
                    display_label = f"[red]Not Connected:[/red] {account_nickname}"
            else:
                display_label = account_nickname
            new_options.append((display_label, name))

        # Determine the label for the currently selected account.
        selected_label = ""
        for label, value in new_options:
            if value == active_account_config:
                selected_label = label
                break

        from textual.widgets import Select

        try:
            old_select = self.query_one("#account_selector", Select)
        except Exception:
            return

        parent_container = old_select.parent
        old_select.remove()
        await asyncio.sleep(0.05)

        new_select = Select(options=new_options, prompt=selected_label, id="account_selector")
        new_select.value = active_account_config

        cast(Any, parent_container).mount(new_select)
        await asyncio.sleep(0)
        new_select.refresh()

    def transition_to_status(self) -> None:
        """Fade out the welcome text then update it with trading system status."""
        welcome_widget = self.query_one("#welcome", Static)
        welcome_widget.add_class("faded")
        self.set_timer(0.5, lambda: self.update_welcome_with_status(welcome_widget))

    def update_welcome_with_status(self, widget: Static) -> None:
        from goldflipper.utils import trading_system_status

        is_running = trading_system_status.is_trading_system_running()
        status_text = "[green]Trading System: Running[/green]" if is_running else "[red]Trading System: Not Running[/red]"
        widget.update(f" {status_text} ")
        widget.remove_class("faded")
        self.set_interval(3, self.refresh_status_in_welcome)

    def refresh_status_in_welcome(self) -> None:
        from goldflipper.utils import trading_system_status

        is_running = trading_system_status.is_trading_system_running()
        status_text = "[green]Trading System: Running[/green]" if is_running else "[red]Trading System: Not Running[/red]"
        widget = self.query_one("#welcome", Static)
        widget.update(f" {status_text} ")

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle account selection changes"""

        selected_account = event.value
        if not isinstance(selected_account, str):
            return
        accounts = config.get("alpaca", "accounts")
        nickname = accounts[selected_account].get("nickname", selected_account.replace("_", " ").title())

        # Use exe-aware settings path
        settings_path = str(get_settings_path())

        # Read the file content as lines and update the active_account.
        with open(settings_path) as file:
            lines = file.readlines()
        for i, line in enumerate(lines):
            if "active_account:" in line:
                indent = len(line) - len(line.lstrip())
                lines[i] = " " * indent + f"active_account: '{selected_account}'  # Specify which account is currently active\n"
                break
        with open(settings_path, "w") as file:
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
        elif event.button.id == "play_creator_gui":
            self.run_gui_play_creator()
        elif event.button.id == "open_chart":
            self.run_chart_viewer()
        elif event.button.id == "get_alpaca_info":
            self.run_get_alpaca_info()
        elif event.button.id == "trade_logger":
            self.run_trade_logger()
        # elif event.button.id == "market_data_compare":
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

        if os.name != "nt":
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
            if is_frozen():
                # Running from exe - use sys.argv[0] (not sys.executable!) for service commands
                # In Nuitka onefile, sys.executable points to python.exe in temp dir
                exe_path = get_exe_path().replace("\\", "\\\\")
                if mode == "install":
                    final_command = f'& "{exe_path}" --service-install; Start-Sleep -Seconds 2; net start GoldflipperService'
                else:
                    final_command = f'net stop GoldflipperService; & "{exe_path}" --service-remove'
            else:
                if mode == "install":
                    # Source mode - use sys.executable path
                    python_path = sys.executable.replace("\\", "\\\\")
                    final_command = f'& "{python_path}" -m goldflipper.run --mode install; Start-Sleep -Seconds 2; net start GoldflipperService'
                else:
                    python_path = sys.executable.replace("\\", "\\\\")
                    final_command = f'net stop GoldflipperService; & "{python_path}" -m goldflipper.run --mode remove'
            ps_command = f"Start-Process powershell -ArgumentList '-NoProfile -Command \"{final_command}\"' -Verb RunAs"
            subprocess.Popen(["powershell", "-Command", ps_command])
            self.notify(f"{'Uninstallation' if service_installed else 'Installation'} initiated. Changes will require a reboot to apply.")

        self.app.push_screen(ConfirmationScreen(message, perform_action))

    def run_option_data_fetcher(self):
        try:
            if is_frozen():
                # Console tool - needs its own console window via subprocess
                subprocess.Popen([get_exe_path(), "--tool", "option_data_fetcher"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                self.notify("Option Data Fetcher launched", severity="information")
            else:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                tools_dir = os.path.join(current_dir, "tools")
                if os.name == "nt":  # Windows
                    subprocess.Popen([sys.executable, os.path.join(tools_dir, "option_data_fetcher.py")], creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:  # Unix-like systems
                    subprocess.Popen(["gnome-terminal", "--", sys.executable, "option_data_fetcher.py"], cwd=tools_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_play_creation_tool(self):
        try:
            if is_frozen():
                # Console tool - needs its own console window via subprocess
                subprocess.Popen([get_exe_path(), "--tool", "play_creation_tool"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                self.notify("Play Creation Tool launched", severity="information")
            else:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                tools_dir = os.path.join(current_dir, "tools")
                if os.name == "nt":
                    subprocess.Popen([sys.executable, os.path.join(tools_dir, "play_creation_tool.py")], creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen(["gnome-terminal", "--", sys.executable, "play_creation_tool.py"], cwd=tools_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_trading_monitor(self):
        try:
            if is_frozen():
                # Running from exe - launch the trading system in a new process
                # using the same exe with a special argument
                # CRITICAL: Use get_exe_path() not sys.executable (wrong in Nuitka onefile)
                if os.name == "nt":
                    # Launch new instance of exe for trading system
                    subprocess.Popen([get_exe_path(), "--trading-mode"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                self.notify("Trading System launched", severity="information")
            else:
                if os.name == "nt":
                    subprocess.Popen([sys.executable, "-m", "goldflipper.run"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen(["gnome-terminal", "--", sys.executable, "-m", "goldflipper.run"])
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_view_plays(self):
        try:
            if is_frozen():
                # view_plays is a Textual app - MUST run as subprocess, not in-thread
                # Two Textual apps cannot run in the same process
                subprocess.Popen([get_exe_path(), "--tool", "view_plays"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                self.notify("View Plays launched", severity="information")
            else:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                tools_dir = os.path.join(current_dir, "tools")
                if os.name == "nt":
                    subprocess.Popen([sys.executable, os.path.join(tools_dir, "view_plays.py")], creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen(["gnome-terminal", "--", sys.executable, "view_plays.py"], cwd=tools_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_system_status(self):
        try:
            if is_frozen():
                subprocess.Popen([get_exe_path(), "--tool", "system_status"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                self.notify("System Status launched", severity="information")
            else:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                tools_dir = os.path.join(current_dir, "tools")
                if os.name == "nt":
                    subprocess.Popen([sys.executable, os.path.join(tools_dir, "system_status.py")], creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen(["gnome-terminal", "--", sys.executable, "system_status.py"], cwd=tools_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_configuration(self):
        """
        Launch the configuration tool to edit settings.yaml.
        """
        import importlib
        import sys

        from goldflipper.tools.configuration import open_settings

        try:
            # Check if this was the first run with a newly created settings file
            was_first_run = settings_just_created

            # Launch the configuration editor
            config_result = open_settings()

            if config_result:
                # Reload the config module to pick up changes
                importlib.reload(sys.modules["goldflipper.config.config"])

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
                        severity="information",
                    )

            # Always refresh the UI to show latest account information
            self.refresh_status_in_welcome()

        except Exception as e:
            self.notify(f"Error launching configuration tool: {e}", severity="error")

    def run_auto_play_creator(self):
        try:
            if is_frozen():
                subprocess.Popen([get_exe_path(), "--tool", "auto_play_creator"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                self.notify("Auto Play Creator launched", severity="information")
            else:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                tools_dir = os.path.join(current_dir, "tools")
                if os.name == "nt":
                    subprocess.Popen([sys.executable, os.path.join(tools_dir, "auto_play_creator.py")], creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen(["gnome-terminal", "--", sys.executable, "auto_play_creator.py"], cwd=tools_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_gui_play_creator(self):
        """Launch the Tkinter GUI Play Creator for multi-strategy play creation."""
        try:
            if is_frozen():
                # Running from exe - import and run in thread
                subprocess.Popen([get_exe_path(), "--tool", "play_creator_gui"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                self.notify("Play Creator GUI launched", severity="information")
            else:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                tools_dir = os.path.join(current_dir, "tools")
                script_path = os.path.join(tools_dir, "play_creator_gui.py")
                # Launch as a standalone process (Tkinter runs its own mainloop)
                subprocess.Popen([sys.executable, script_path], cwd=tools_dir)
                self.notify("Play Creator GUI launched", severity="information")
        except Exception as e:
            self.notify(f"Error launching GUI: {str(e)}", severity="error")

    def run_chart_viewer(self):
        try:
            if is_frozen():
                subprocess.Popen([get_exe_path(), "--tool", "chart_viewer"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                self.notify("Chart Viewer launched", severity="information")
            else:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                chart_dir = os.path.join(current_dir, "chart")
                if os.name == "nt":
                    subprocess.Popen([sys.executable, os.path.join(chart_dir, "chart_viewer.py")], creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen(["gnome-terminal", "--", sys.executable, "chart_viewer.py"], cwd=chart_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_get_alpaca_info(self):
        try:
            if is_frozen():
                # Console app that uses terminal output - run as subprocess
                subprocess.Popen([get_exe_path(), "--tool", "get_alpaca_info"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                self.notify("Alpaca Info launched", severity="information")
            else:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                tools_dir = os.path.join(current_dir, "tools")
                if os.name == "nt":
                    subprocess.Popen([sys.executable, os.path.join(tools_dir, "get_alpaca_info.py")], creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen(["gnome-terminal", "--", sys.executable, "get_alpaca_info.py"], cwd=tools_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_trade_logger(self):
        try:
            if is_frozen():
                # Tkinter app - run as subprocess for cleaner separation
                subprocess.Popen([get_exe_path(), "--tool", "trade_logger"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                self.notify("Trade Logger launched", severity="information")
            else:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                logging_dir = os.path.join(current_dir, "trade_logging")
                if os.name == "nt":
                    subprocess.Popen([sys.executable, os.path.join(logging_dir, "trade_logger_ui.py")], creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen(["gnome-terminal", "--", sys.executable, "trade_logger_ui.py"], cwd=logging_dir)
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def run_upload_template(self) -> None:
        """
        Prompts the user to select a CSV file and launches the multi-strategy CSV ingestion tool.
        The tool auto-detects strategy from CSV content and saves resulting plays to appropriate folders.
        Supports: option_swings, momentum, sell_puts CSV formats.
        """
        import os
        import subprocess
        import threading

        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()  # Hide the root window.
            file_path = filedialog.askopenfilename(title="Select CSV Template", filetypes=[("CSV Files", "*.csv")])
            root.destroy()
        except Exception as e:
            self.notify(f"File dialog error: {e}")
            file_path = input("Enter CSV file path: ").strip()

        if not file_path:
            self.notify("No file selected, upload aborted.")
            return

        if is_frozen():
            # Running from exe - import and run module with file_path argument
            def run_ingestion():
                try:
                    # Set sys.argv to pass the file path
                    import sys

                    from goldflipper.tools import play_csv_ingestion_multitool

                    old_argv = sys.argv
                    sys.argv = ["play_csv_ingestion_multitool.py", file_path]
                    try:
                        if hasattr(play_csv_ingestion_multitool, "main"):
                            play_csv_ingestion_multitool.main()
                    finally:
                        sys.argv = old_argv
                except Exception as e:
                    import logging

                    logging.error(f"Error running CSV ingestion: {e}")

            thread = threading.Thread(target=run_ingestion, daemon=True)
            thread.start()
            self.notify("CSV Ingestion Tool launched", severity="information")
        else:
            # Use the multi-strategy CSV ingestion tool
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tools_dir = os.path.join(current_dir, "tools")

            if os.name == "nt":  # Windows
                subprocess.Popen(
                    [sys.executable, os.path.join(tools_dir, "play_csv_ingestion_multitool.py"), file_path],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:  # Unix-like systems
                subprocess.Popen(
                    ["gnome-terminal", "--", sys.executable, os.path.join(tools_dir, "play_csv_ingestion_multitool.py"), file_path], cwd=tools_dir
                )


class GoldflipperTUI(App):
    CSS = """
    Screen {
        align: center middle;
        background: $surface;
        min-width: 120;
        min-height: 120;
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
        border: solid $accent;
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
        border: solid $accent;
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
        border: solid $accent;
    }

    .container {
        width: 90%;
        height: auto;
        align: center middle;
        background: $surface-darken-2;
        border: solid $primary;
        padding: 1;
        margin-top: 1;
    }

    #button_container {
        width: 100%;
        height: auto;
        align: center middle;
        padding: 0;
    }

    .button-column {
        width: 33%;
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
        # Force a full refresh to clear any rendering artifacts from resize
        self.refresh(repaint=True)
        self.push_screen(WelcomeScreen())
        # NOTE: Window maximization disabled - causes desktop freezes when combined
        # with Tkinter dialogs (e.g., Upload Template file picker).
        # Uncomment to test: self.set_timer(0.5, self._deferred_maximize)

    def _deferred_maximize(self) -> None:
        """Maximize the console window after Textual is fully initialized."""
        maximize_console_window()
        self.refresh(repaint=True)  # Refresh to adapt to new window size


def resize_terminal(cols: int = 120, rows: int = 40) -> None:
    """Resize the terminal window on Windows to a reasonable initial size.

    Must be called BEFORE Textual takes over the terminal.
    This sets a good starting size; maximization is handled separately
    after Textual is fully initialized (see GoldflipperTUI.on_mount).
    """
    if os.name != "nt":
        return

    # Method 1: ANSI escape codes for size (Windows Terminal - preferred)
    try:
        sys.stdout.write(f"\x1b[8;{rows};{cols}t")
        sys.stdout.flush()
        time.sleep(0.5)  # Small delay to let terminal resize
    except Exception:
        pass

    # Method 2: mode command (legacy conhost fallback)
    try:
        os.system(f"mode con: cols={cols} lines={rows}")
    except Exception:
        pass


def maximize_console_window() -> bool:
    """Maximize the console window using Windows API.

    This should be called AFTER Textual has fully initialized to avoid
    conflicts between the maximized window state and Tkinter dialogs.

    Returns True if maximization succeeded, False otherwise.
    """
    if os.name != "nt":
        return False

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        # Get console window handle
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            SW_MAXIMIZE = 3
            user32.ShowWindow(hwnd, SW_MAXIMIZE)
            return True
    except Exception:
        pass

    return False


if __name__ == "__main__":
    resize_terminal(120, 40)
    app = GoldflipperTUI()
    app.run()
