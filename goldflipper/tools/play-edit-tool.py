import os
import json
import platform
import argparse
from datetime import datetime
from pathlib import Path

def get_input(prompt, type_cast=str, validation=None, error_message=None, optional=False):
    """Helper function to get and validate user input"""
    while True:
        value = input(prompt)
        if optional and not value:
            return None
        try:
            value = type_cast(value)
            if validation and not validation(value):
                print(error_message or "Invalid input")
                continue
            return value
        except ValueError:
            print(error_message or "Invalid input")

def load_play(filepath):
    """Load a play from JSON file"""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading play: {e}")
        return None

def save_play(filepath, play_data):
    """Save play data back to JSON file"""
    try:
        with open(filepath, 'w') as f:
            json.dump(play_data, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving play: {e}")
        return False

def get_all_plays():
    """Get all plays from all folders"""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../plays"))
    folders = ['new', 'open', 'closed', 'temp', 'expired']
    plays = []
    
    for folder in folders:
        folder_path = os.path.join(base_dir, folder)
        if os.path.exists(folder_path):
            for file in os.listdir(folder_path):
                if file.endswith('.json'):
                    filepath = os.path.join(folder_path, file)
                    plays.append({
                        'filepath': filepath,
                        'folder': folder,
                        'filename': file
                    })
    return plays

def find_play_file(filename):
    """Locate a play file across all play folders"""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../plays"))
    folders = ['new', 'open', 'closed', 'temp', 'expired']
    
    for folder in folders:
        filepath = os.path.join(base_dir, folder, filename)
        if os.path.exists(filepath):
            return {
                'filepath': filepath,
                'folder': folder,
                'filename': filename
            }
    return None

def edit_play_field(play_data, field):
    """Edit a specific field in the play data"""
    current_value = play_data.get(field, "N/A")
    print(f"\nCurrent {field}: {current_value}")
    
    if isinstance(current_value, dict):
        for key in current_value:
            new_value = get_input(
                f"Enter new value for {field}.{key} (press Enter to keep current): ",
                type_cast=type(current_value[key]),
                optional=True
            )
            if new_value is not None:
                current_value[key] = new_value
    else:
        new_value = get_input(
            f"Enter new value for {field} (press Enter to keep current): ",
            type_cast=type(current_value) if current_value != "N/A" else str,
            optional=True
        )
        if new_value is not None:
            play_data[field] = new_value

def edit_play():
    """Main function to edit plays"""
    plays = get_all_plays()
    if not plays:
        print("No plays found")
        return

    # Display available plays
    print("\nAvailable Plays:")
    for i, play in enumerate(plays, 1):
        print(f"{i}. [{play['folder']}] {play['filename']}")

    # Get play selection
    selection = get_input(
        "\nEnter the number of the play to edit (0 to exit): ",
        type_cast=int,
        validation=lambda x: 0 <= x <= len(plays),
        error_message=f"Please enter a number between 0 and {len(plays)}"
    )

    if selection == 0:
        return

    selected_play = plays[selection - 1]
    play_data = load_play(selected_play['filepath'])
    
    if not play_data:
        return

    while True:
        print("\nEditable Fields:")
        fields = [
            "symbol", "trade_type", "entry_point", "strike_price",
            "expiration_date", "play_expiration_date", "take_profit",
            "stop_loss", "contracts", "play_class"
        ]
        
        for i, field in enumerate(fields, 1):
            print(f"{i}. {field}")
        
        field_selection = get_input(
            "\nEnter the number of the field to edit (0 to save and exit): ",
            type_cast=int,
            validation=lambda x: 0 <= x <= len(fields),
            error_message=f"Please enter a number between 0 and {len(fields)}"
        )

        if field_selection == 0:
            break

        edit_play_field(play_data, fields[field_selection - 1])

    # Save changes
    if save_play(selected_play['filepath'], play_data):
        print(f"\nChanges saved to {selected_play['filename']}")
    else:
        print("\nFailed to save changes")

def edit_specific_play(filename):
    """Edit a specific play file"""
    play_info = find_play_file(filename)
    
    if not play_info:
        print(f"Error: Play file '{filename}' not found")
        return
    
    print(f"\nEditing play: [{play_info['folder']}] {play_info['filename']}")
    play_data = load_play(play_info['filepath'])
    
    if not play_data:
        return

    while True:
        print("\nEditable Fields:")
        fields = [
            "symbol", "trade_type", "entry_point", "strike_price",
            "expiration_date", "play_expiration_date", "take_profit",
            "stop_loss", "contracts", "play_class"
        ]
        
        for i, field in enumerate(fields, 1):
            print(f"{i}. {field}")
        
        field_selection = get_input(
            "\nEnter the number of the field to edit (0 to save and exit): ",
            type_cast=int,
            validation=lambda x: 0 <= x <= len(fields),
            error_message=f"Please enter a number between 0 and {len(fields)}"
        )

        if field_selection == 0:
            break

        edit_play_field(play_data, fields[field_selection - 1])

    # Save changes
    if save_play(play_info['filepath'], play_data):
        print(f"\nChanges saved to {play_info['filename']}")
    else:
        print("\nFailed to save changes")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', help='Specific play file to edit')
    args = parser.parse_args()

    if args.file:
        # Edit specific file
        edit_specific_play(args.file)
    else:
        # Show selection menu
        edit_play()

if __name__ == "__main__":
    main()