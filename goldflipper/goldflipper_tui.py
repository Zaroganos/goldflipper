from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Button, Static
from textual.screen import Screen
import subprocess
import sys
import os
from pathlib import Path

class WelcomeScreen(Screen):
    BINDINGS = [("q", "quit", "Quit")]
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(" Welcome to Goldflipper Trading System ", id="welcome"),
            Horizontal(
                Container(
                    Button("Create New Play", variant="primary", id="create_play"),
                    Button("Fetch Option Data", variant="primary", id="option_data_fetcher"),
                    Button("Launch Trading System", variant="success", id="start_monitor"),
                    Button("Auto Play Creator", variant="primary", id="auto_play_creator"),
                    classes="button-column",
                ),
                Container(
                    Button("View / Edit Current Plays", variant="primary", id="view_plays"),
                    Button("Upkeep and Status", variant="primary", id="system_status"),
                    Button("Configuration", variant="primary", id="configuration"),
                    Button("Placeholder 2", variant="primary", id="placeholder2"),
                    classes="button-column",
                ),
                id="button_container"
            ),
            classes="container",
        )
        yield Footer()

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
        elif event.button.id == "exit":
            self.app.exit()

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

class GoldflipperTUI(App):
    CSS = """
    Screen {
        align: center middle;
        background: $surface;
    }

    #welcome {
        margin: 1;
        padding: 2;
        text-align: center;
        width: 100%;
        color: gold;
        background: $surface;
        text-style: bold;
        border: heavy $accent;
    }
    
    .container {
        width: 90%;
        height: auto;
        align: center middle;
        background: $surface-darken-2;
        border: panel $primary;
        padding: 2;
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