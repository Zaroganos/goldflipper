import os
import json
from datetime import datetime
import subprocess
import platform
from pathlib import Path

''' This is the old version of the play viewer.
It is being superseded by the new TUI version.
However, because the TUI version isn't rendering correctly,
this version is being kept as a backup. '''

def open_file_explorer(path):
    """
    Opens the file explorer at the specified path based on the operating system
    """
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":  # macOS
        subprocess.run(["open", path])
    else:  # Linux
        subprocess.run(["xdg-open", path])

def format_play_files(folder_path):
    """
    Formats and returns the play files in a given folder
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

def view_plays():
    """
    Tool to view and manage current plays in the system.
    """
    # Get the plays directory path
    plays_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../plays"))
    
    # Open file explorer
    print("\nOpening plays directory in file explorer...")
    open_file_explorer(plays_dir)
    
    # Display plays
    print("\nCurrent Plays Status")
    print("===================")
    
    # Define folders to check
    folders = ['New', 'Open', 'Closed', 'Temp', 'Expired'] # Not checking 'Old' folder
    
    for folder in folders:
        folder_path = os.path.join(plays_dir, folder)
        plays = format_play_files(folder_path)
        
        print(f"\n{folder} Plays")
        print("-" * (len(folder) + 6))
        
        if not plays:
            print("No plays found")
            continue
            
        for play in plays:
            data = play['data']
            print(f"\n📄 {play['filename']}")
            print(f"   Symbol: ${data.get('symbol', 'N/A')}")
            print(f"   Created On: {data.get('creation_date', 'N/A')} -> Play Expiration: {data.get('play_expiration_date', 'N/A')} -> Contract Expiration: {data.get('expiration_date', 'N/A')}")
            print(f"   Entry Price: ${data.get('entry_point', 0.00):.2f} -> Strike Price: ${data.get('strike_price', 'N/A')} -> TP: ${data.get('take_profit', {}).get('stock_price', 0.00):.2f} | SL: ${data.get('stop_loss', {}).get('stock_price', 0.00):.2f}")
            print(f"   Strategy: {data.get('strategy', 'Option Swings')}")
            print("   " + "-" * 30) # Prints a separator line '-----'
            # TODO: Add more details to the play view🟢🔴

if __name__ == "__main__":
    view_plays() 