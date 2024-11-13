import os
import json
from datetime import datetime
import subprocess
import platform
from pathlib import Path

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
    folders = ['New', 'Open', 'Closed', 'Expired']
    
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
            print(f"   Strategy: {data.get('strategy', 'Option Swings')}")
            print(f"   Entry Price: ${data.get('entry_point', 0.00):.2f}")
            print(f"   Creation Date: {data.get('creation_date', 'N/A')}")
            print("   " + "-" * 30)
            # TODO: Add more details to the play view🟢🔴

if __name__ == "__main__":
    view_plays() 