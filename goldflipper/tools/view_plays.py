import os
import json
import subprocess
import platform
import yaml
from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Button
from textual.containers import Container, Horizontal
from textual.widget import Widget
from rich.text import Text

def open_file_explorer(path):
    """
    Opens the file explorer at the specified path based on the operating system.
    """
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":  # macOS
        subprocess.run(["open", path])
    else:  # Linux
        subprocess.run(["xdg-open", path])

def format_play_files(folder_path):
    """
    Formats and returns the play files in a given folder.
    """
    plays = []
    if os.path.exists(folder_path):
        for file in os.listdir(folder_path):
            if file.endswith('.json'):
                try:
                    with open(os.path.join(folder_path, file), 'r') as f:
                        play_data = json.load(f)
                        plays.append({
                            'filename': file,
                            'data': play_data
                        })
                except json.JSONDecodeError:
                    print(f"Error reading {file}")
    return plays

def format_price_value(price_data):
    """Format price data to display either stock price or premium percentage."""
    if price_data.get('stock_price') is not None:
        stock_price = price_data['stock_price']
        if isinstance(stock_price, list):
            # For contingency orders, show both values
            return f"${float(stock_price[0]):.2f} | ${float(stock_price[1]):.2f}"
        return f"${float(stock_price):.2f}"
    elif price_data.get('premium_pct') is not None:
        premium_pct = price_data['premium_pct']
        if isinstance(premium_pct, list):
            # For contingency orders, show both values
            return f"{float(premium_pct[0]):.0f}% | {float(premium_pct[1]):.0f}%"
        return f"{float(premium_pct):.0f}%"
    return "N/A"

def format_date(date_str):
    """Convert YYYY-MM-DD to MM/DD/YYYY format."""
    if date_str and date_str != 'N/A':
        try:
            year, month, day = date_str.split('-')
            return f"{month}/{day}/{year}"
        except ValueError:
            return date_str
    return date_str

class PlayCard(Widget):
    """
    A custom widget to display play details in a card format.
    """
    def __init__(self, play):
        super().__init__()
        self.play = play

    def compose(self) -> ComposeResult:
        with Horizontal():
            data = self.play['data']
            name = data.get('play_name', 'N/A')
            entry_point = data.get('entry_point', {})
            entry_price = float(entry_point.get('stock_price', 0.00))
            strike_price = data.get('strike_price', 'N/A')
            
            # Handle both price formats
            tp_value = format_price_value(data.get('take_profit', {}))
            sl_value = format_price_value(data.get('stop_loss', {}))
            
            symbol = data.get('symbol', 'N/A')
            creation_date = format_date(data.get('creation_date', 'N/A'))
            play_expiration = format_date(data.get('play_expiration_date', 'N/A'))
            expiration_date = format_date(data.get('expiration_date', 'N/A'))
            strategy = data.get('strategy', 'Option Swings')
            entry_order = data.get('entry_point', {}).get('order_type', 'N/A')
            tp_order = data.get('take_profit', {}).get('order_type', 'N/A')
            sl_order = data.get('stop_loss', {}).get('order_type', 'N/A')
            sl_contingency_order = data.get('stop_loss', {}).get('order_type', 'N/A')
            if isinstance(sl_contingency_order, list) and len(sl_contingency_order) > 1:
                sl_order = f"{sl_contingency_order[0]} [white]-> Contingency:[/white] {sl_contingency_order[1]}"

            details = (
                f"📄  [bold green]{name}[/bold green]\n"
                f"[bold yellow]${symbol}[/bold yellow] - [cyan]{strategy}[/cyan]\n"
                f"[white]Contract Exp.:[/white] {expiration_date}  "
                f"[purple]Strike:[/purple] {strike_price}\n"
                f"[color(33)]Entry:[/color(33)] ${entry_price:.2f} [white]->[/white] "
                f"[green]TP:[/green] {tp_value} | "
                f"[red]SL:[/red] {sl_value}\n"
                f"[white]Entry:[/white] {entry_order} [white]->[/white] "
                f"[white]TP:[/white] {tp_order} [white]|[/white] "
                f"[white]SL:[/white] {sl_order}\n"
                f"[white]Created:[/white] {creation_date} [white]->[/white] "
                f"[white]Play Exp.:[/white] {play_expiration}\n"


            ).strip()  # Strip leading/trailing whitespace from the string

            # Create a Text object from the stripped string
            text_details = Text.from_markup(details)

            yield Static(text_details, classes="play-details")
            yield Button("✏️ Edit", id=f"edit_{os.path.splitext(self.play['filename'])[0]}", classes="edit-button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id.startswith("edit_"):
            filename = f"{event.button.id.replace('edit_', '')}.json"
            self.launch_editor(filename)

    def launch_editor(self, filename: str) -> None:
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            editor_path = os.path.join(current_dir, "play-edit-tool.py")
            
            if os.name == 'nt':  # Windows
                cmd = ['cmd', '/k', 'python', editor_path, '--file', filename]
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:  # Unix-like systems
                subprocess.Popen(['gnome-terminal', '--', 'python', editor_path, '--file', filename])
        except Exception as e:
            self.app.notify(f"Error launching editor: {str(e)}", severity="error")

class ViewPlaysApp(App):
    CSS = '''
    Screen {
        align: center middle;
        background: #1b1b1b;
    }
    
    #folder_button {
        dock: top;
        width: 100%;
        height: 3;
        margin: 1 0;
        background: #3b3b3b;
        color: gold;
        text-align: center;
        text-style: bold;
        layer: overlay;
    }
    
    #folder_button:hover {
        background: #4b4b4b;
    }
    
    #plays_container {
        overflow-y: auto;
        height: 100%;
        width: 100%;
        padding: 0;
        margin-top: 4;
    }
    
    .play-card {
        width: 100%;
        border: solid gold;
        padding: 0 1 0 1;
        margin: 1 1 1 2;
        height: auto;
        background: #2b2b2b;
    }
    
    .folder-title {
        content-align: center middle;
        color: #FFD700;
        height: 10;
        margin: 1 1 1 1;
    }
    
    .edit-button {
        dock: left;
        width: 15;
        margin: 0 3 0 3;
        background: #3b3b3b;
        color: gold;
    }
    
    .edit-button:hover {
        background: #4b4b4b;
    }
    '''

    def compose(self) -> ComposeResult:
        yield Header()
        yield Button("📁 Open Plays Folder", id="folder_button")
        yield Container(id="plays_container")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "folder_button":
            plays_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../plays"))
            open_file_explorer(plays_dir)

    async def on_mount(self):
        await self.load_plays()

    async def load_plays(self):
        # Load settings
        config_path = os.path.join(os.path.dirname(__file__), "../config/settings.yaml")
        with open(config_path, 'r') as f:
            settings = yaml.safe_load(f)
        
        # Get enabled folders from config
        enabled_folders = settings['viewer']['enabled_folders']
        folder_order = settings['viewer']['folder_order']
        
        # Use folder_order for display, but only show enabled folders
        folders = [folder for folder in folder_order if folder in enabled_folders]
        
        plays_container = self.query_one("#plays_container")

        while plays_container.children:
            child = plays_container.children[0]
            plays_container.remove(child)

        for folder in folders:
            folder_path = os.path.join(os.path.dirname(__file__), "../plays", folder.lower())
            plays = format_play_files(folder_path)

            title_text = f"{folder.title()} Plays"  # Capitalize folder name
            plays_container.mount(Static(f"\n{title_text}\n", classes="folder-title"))

            if not plays:
                plays_container.mount(Static("No plays found", classes="play-card"))
                continue

            for play in plays:
                play_card = PlayCard(play)
                plays_container.mount(play_card)

if __name__ == "__main__":
    app = ViewPlaysApp()
    app.run()