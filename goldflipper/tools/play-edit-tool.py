import os
import json
import platform
import argparse
from datetime import datetime, timedelta
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

def edit_play_field(play_data, field, filepath):
    """Edit a specific field in the play data"""
    if field == 'expiration_date':
        # Only allow editing for plays in 'new' folder
        if '/new/' not in filepath:
            print("\nERROR: Expiration date can only be modified for plays in the 'new' folder")
            return
            
        confirm = get_input(
            "\nWARNING: Changing expiration date will affect the option contract symbol. Continue? (y/N): ",
            str,
            validation=lambda x: x.lower() in ['y', 'n', ''],
            error_message="Please enter 'y' or 'n'"
        )
        if confirm.lower() != 'y':
            return
            
        new_value = get_input(
            "Enter new expiration date (MM/DD/YYYY): ",
            str,
            validation=lambda x: datetime.strptime(x, "%m/%d/%Y"),
            error_message="Please enter a valid date in MM/DD/YYYY format"
        )
        
        if new_value:
            old_date = datetime.strptime(play_data['expiration_date'], "%m/%d/%Y")
            new_date = datetime.strptime(new_value, "%m/%d/%Y")
            
            # Update contract symbol date portion
            old_date_str = old_date.strftime("%y%m%d")
            new_date_str = new_date.strftime("%y%m%d")
            play_data['expiration_date'] = new_value
            play_data['option_contract_symbol'] = play_data['option_contract_symbol'].replace(
                old_date_str, new_date_str
            )
            
    elif field == 'play_expiration_date':
        new_value = get_input(
            "Enter new play expiration date (MM/DD/YYYY): ",
            str,
            validation=lambda x: datetime.strptime(x, "%m/%d/%Y"),
            error_message="Please enter a valid date in MM/DD/YYYY format"
        )
        
        if new_value:
            new_date = datetime.strptime(new_value, "%m/%d/%Y")
            future_date = datetime.now() + timedelta(days=30)
            
            if new_date > future_date:
                confirm = get_input(
                    "\nWARNING: Date is more than 30 days in the future. Continue? (y/N): ",
                    str,
                    validation=lambda x: x.lower() in ['y', 'n', ''],
                    error_message="Please enter 'y' or 'n'"
                )
                if confirm.lower() != 'y':
                    return
                    
            play_data['play_expiration_date'] = new_value
            
    elif field == 'take_profit':
        price_type = get_input(
            "Enter price type (1 for stock price, 2 for option premium %): ",
            int,
            validation=lambda x: x in [1, 2],
            error_message="Please enter 1 for stock price or 2 for option premium %"
        )
        
        if price_type == 1:
            price = get_input(
                "Enter take profit stock price: ",
                float,
                error_message="Please enter a valid number"
            )
            if price is not None:
                play_data['take_profit']['stock_price'] = price
                
        else:
            premium = get_input(
                "Enter take profit premium percentage: ",
                float,
                validation=lambda x: 0 < x <= 100,
                error_message="Please enter a percentage between 0 and 100"
            )
            if premium is not None:
                play_data['take_profit']['premium_pct'] = premium

    elif field == 'stop_loss':
        price_type = get_input(
            "Enter price type (1 for stock price, 2 for option premium %): ",
            int,
            validation=lambda x: x in [1, 2],
            error_message="Please enter 1 for stock price or 2 for option premium %"
        )
        
        if price_type == 1:
            price = get_input(
                "Enter stop loss stock price: ",
                float,
                error_message="Please enter a valid number"
            )
            if price is not None:
                play_data['stop_loss']['stock_price'] = price
                
        else:
            premium = get_input(
                "Enter stop loss premium percentage: ",
                float,
                validation=lambda x: 0 < x <= 100,
                error_message="Please enter a percentage between 0 and 100"
            )
            if premium is not None:
                play_data['stop_loss']['premium_pct'] = premium

    elif field == 'contracts':
        # Only allow editing for plays in 'new' folder
        if '/new/' not in filepath:
            print("\nERROR: Number of contracts can only be modified for plays in the 'new' folder")
            return
            
        new_value = get_input(
            "Enter number of contracts: ",
            int,
            validation=lambda x: x > 0,
            error_message="Please enter a positive number"
        )
        if new_value is not None:
            play_data['contracts'] = new_value

    elif field == 'play_class':
        # Only allow editing for plays in 'new' folder
        if '/new/' not in filepath:
            print("\nERROR: Play class can only be modified for plays in the 'new' folder")
            return
            
        edit_play_class(play_data)
        return
    elif field == 'conditional_plays':
        edit_conditional_plays(play_data, filepath)
        return

    current_value = play_data.get(field, "Not set")
    print(f"\nCurrent value of {field}: {current_value}")

    if field == 'symbol':
        # Confirm symbol change
        confirm = get_input(
            "\nWARNING: Changing the symbol will affect the option contract symbol. Are you sure? (y/N): ",
            str,
            validation=lambda x: x.lower() in ['y', 'n', ''],
            error_message="Please enter 'y' or 'n'"
        )
        if confirm.lower() != 'y':
            return

        new_value = get_input(
            "Enter new symbol: ",
            str,
            validation=lambda x: len(x) > 0,
            error_message="Symbol cannot be empty"
        ).upper()

        if new_value:
            # Update option contract symbol
            old_symbol = play_data['symbol']
            play_data['symbol'] = new_value
            play_data['option_contract_symbol'] = play_data['option_contract_symbol'].replace(
                old_symbol, new_value
            )

    elif field == 'trade_type':
        # Confirm trade type change
        confirm = get_input(
            "\nWARNING: Changing trade type will affect the option contract symbol. Are you sure? (y/N): ",
            str,
            validation=lambda x: x.lower() in ['y', 'n', ''],
            error_message="Please enter 'y' or 'n'"
        )
        if confirm.lower() != 'y':
            return

        new_value = get_input(
            "Enter trade type (CALL or PUT): ",
            str,
            validation=lambda x: x.upper() in ['CALL', 'PUT'],
            error_message="Please enter CALL or PUT"
        ).upper()

        if new_value:
            # Update option contract symbol
            old_type = 'C' if play_data['trade_type'] == 'CALL' else 'P'
            new_type = 'C' if new_value == 'CALL' else 'P'
            play_data['trade_type'] = new_value
            play_data['option_contract_symbol'] = play_data['option_contract_symbol'].replace(
                old_type, new_type
            )

    elif field == 'entry_point':
        new_value = get_input(
            "Enter the entry price (stock price): ",
            float,
            error_message="Please enter a valid number for the entry price."
        )
        if new_value is not None:
            play_data['entry_point'] = new_value

    elif field == 'strike_price':
        new_value = get_input(
            "Enter the strike price: ",
            float,
            error_message="Please enter a valid number for the strike price."
        )
        if new_value is not None:
            play_data['strike_price'] = str(new_value)  # Store as string like in creation tool

    else:
        new_value = get_input(
            f"Enter new value for {field} (press Enter to keep current): ",
            optional=True
        )
        if new_value is not None:
            play_data[field] = new_value

def display_plays_list(plays, source_folder, current_play_filename):
    """Display numbered list of available plays from folder, excluding current play"""
    print(f"\nAvailable plays in {source_folder} folder:")
    filtered_plays = [p for p in plays if p['filename'] != current_play_filename]
    
    for idx, play in enumerate(filtered_plays, 1):
        print(f"{idx}. {play['filename']}")
    return filtered_plays

def select_plays_from_list(plays):
    """Let user select multiple plays from displayed list, preventing duplicates"""
    selected = []
    while True:
        choice = get_input(
            "\nEnter play number to add (or press Enter to finish): ",
            type_cast=str,
            optional=True
        )
        if not choice:
            break
            
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(plays):
                filename = plays[idx]['filename']
                if filename not in selected:
                    selected.append(filename)
                else:
                    print("Play already selected")
            else:
                print("Invalid play number")
        except ValueError:
            print("Please enter a valid number")
    
    return selected

def edit_play_class(play_data):
    """Edit play class type (SIMPLE/PRIMARY/OTO)"""
    print("\n=== Play Class Editor ===")
    print("\nValid play classes:")
    print("1. SIMPLE  - Standard play")
    print("2. PRIMARY - Primary play in OCO relationship")
    print("3. OTO     - One-Triggers-Other play")
    
    current = play_data.get('play_class', 'SIMPLE')
    print(f"\nCurrent play class: {current}")
    
    choice = get_input(
        "\nSelect play class (1-3 or Enter to keep current): ",
        type_cast=str,
        optional=True
    )
    
    if choice:
        try:
            choice = int(choice)
            if choice == 1:
                play_data['play_class'] = 'SIMPLE'
            elif choice == 2:
                play_data['play_class'] = 'PRIMARY'
            elif choice == 3:
                play_data['play_class'] = 'OTO'
            else:
                print("Invalid choice")
        except ValueError:
            print("Please enter a valid number")

def edit_conditional_plays(play_data, filepath):
    """Edit OCO/OTO triggers in conditional_plays field"""
    current_filename = os.path.basename(filepath)
    
    while True:
        print("\n=== Conditional Plays Editor ===")
        print("\nCurrent Configuration:")
        
        # Initialize conditional_plays with proper structure if missing or incomplete
        if 'conditional_plays' not in play_data:
            play_data['conditional_plays'] = {}
            
        if not isinstance(play_data['conditional_plays'], dict):
            play_data['conditional_plays'] = {}
            
        # Ensure both trigger fields exist
        if 'OCO_trigger' not in play_data['conditional_plays']:
            play_data['conditional_plays']['OCO_trigger'] = None
        if 'OTO_trigger' not in play_data['conditional_plays']:
            play_data['conditional_plays']['OTO_trigger'] = None
        
        # Display current triggers safely
        print("\nOCO Trigger Play:")
        print(f"  {play_data['conditional_plays'].get('OCO_trigger', 'None configured')}")
            
        print("\nOTO Trigger Play:")
        print(f"  {play_data['conditional_plays'].get('OTO_trigger', 'None configured')}")
            
        print("\nOptions:")
        print("1. Edit OCO trigger play")
        print("2. Edit OTO trigger play") 
        print("3. Done")
        
        choice = get_input(
            "\nSelect option (1-3): ",
            type_cast=int,
            validation=lambda x: x in [1,2,3],
            error_message="Please enter 1, 2 or 3"
        )
        
        if choice == 3:
            break
            
        all_plays = get_all_plays()
        
        if choice == 1:
            print("\n=== Edit OCO Trigger ===")
            print("OCO play will be cancelled when this play executes")
            new_plays = [p for p in all_plays if p['folder'] == 'new']
            available = display_plays_list(new_plays, 'new', current_filename)
            selected = select_single_play(available)
            if selected:
                play_data['conditional_plays']['OCO_trigger'] = selected
                print("\nOCO trigger updated successfully")
                
        elif choice == 2:
            print("\n=== Edit OTO Trigger ===")
            print("OTO play will be triggered when this play executes")
            temp_plays = [p for p in all_plays if p['folder'] == 'temp']
            available = display_plays_list(temp_plays, 'temp', current_filename)
            selected = select_single_play(available)
            if selected:
                play_data['conditional_plays']['OTO_trigger'] = selected
                print("\nOTO trigger updated successfully")
    
    # Save changes
    if save_play(filepath, play_data):
        print("\nConditional plays configuration saved successfully")
    else:
        print("\nError: Failed to save changes")

def select_single_play(plays):
    """Let user select a single play from the list"""
    while True:
        choice = get_input(
            "\nEnter play number to select (or press Enter to cancel): ",
            type_cast=str,
            optional=True
        )
        if not choice:
            return None
            
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(plays):
                return plays[idx]['filename']
            else:
                print("Invalid play number")
        except ValueError:
            print("Please enter a valid number")

def edit_oco_trigger(play_data, filepath):
    """Edit OCO trigger play"""
    current_filename = os.path.basename(filepath)
    current_trigger = play_data['conditional_plays'].get('OCO_trigger')
    
    print("\n=== Edit OCO Trigger ===")
    print(f"Current OCO trigger: {current_trigger or 'None'}")
    print("\nOptions:")
    print("1. Add/Change OCO trigger")
    print("2. Remove OCO trigger")
    print("3. Cancel")
    
    choice = get_input(
        "\nSelect option (1-3): ",
        type_cast=int,
        validation=lambda x: x in [1,2,3],
        error_message="Please enter 1, 2 or 3"
    )
    
    if choice == 1:
        print("\nSelect new OCO trigger play:")
        new_plays = [p for p in get_all_plays() if p['folder'] == 'new']
        available = display_plays_list(new_plays, 'new', current_filename)
        selected = select_single_play(available)
        if selected:
            play_data['conditional_plays']['OCO_trigger'] = selected
            print("\nOCO trigger updated successfully")
            
    elif choice == 2:
        if current_trigger:
            play_data['conditional_plays']['OCO_trigger'] = None
            print("\nOCO trigger removed")
        else:
            print("\nNo OCO trigger to remove")

def edit_oto_trigger(play_data, filepath):
    """Edit OTO trigger play"""
    current_filename = os.path.basename(filepath)
    current_trigger = play_data['conditional_plays'].get('OTO_trigger')
    
    print("\n=== Edit OTO Trigger ===")
    print(f"Current OTO trigger: {current_trigger or 'None'}")
    print("\nOptions:")
    print("1. Add/Change OTO trigger")
    print("2. Remove OTO trigger")
    print("3. Cancel")
    
    choice = get_input(
        "\nSelect option (1-3): ",
        type_cast=int,
        validation=lambda x: x in [1,2,3],
        error_message="Please enter 1, 2 or 3"
    )
    
    if choice == 1:
        print("\nSelect new OTO trigger play:")
        temp_plays = [p for p in get_all_plays() if p['folder'] == 'temp']
        available = display_plays_list(temp_plays, 'temp', current_filename)
        selected = select_single_play(available)
        if selected:
            play_data['conditional_plays']['OTO_trigger'] = selected
            print("\nOTO trigger updated successfully")
            
    elif choice == 2:
        if current_trigger:
            play_data['conditional_plays']['OTO_trigger'] = None
            print("\nOTO trigger removed")
        else:
            print("\nNo OTO trigger to remove")

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
            "stop_loss", "contracts", "play_class", "conditional_plays"
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

        edit_play_field(play_data, fields[field_selection - 1], selected_play['filepath'])

        if fields[field_selection - 1] == 'play_class':
            edit_play_class(play_data)

        if fields[field_selection - 1] == 'conditional_plays':
            edit_conditional_plays(play_data, selected_play['filepath'])

    # Save changes
    if save_play(selected_play['filepath'], play_data):
        print(f"\nChanges saved to {selected_play['filename']}")
    else:
        print("\nFailed to save changes")

def rename_play(play_data, play_info):
    """Rename a play and its file"""
    current_name = play_data.get('play_name', '')
    print(f"\nCurrent play name: {current_name}")
    
    new_name = get_input(
        "Enter new play name: ",
        str,
        validation=lambda x: len(x.strip()) > 0,
        error_message="Play name cannot be empty"
    )
    
    if new_name:
        try:
            # Update play data
            play_data['play_name'] = new_name
            
            # Generate new filename (keep same extension)
            old_filepath = play_info['filepath']
            new_filename = f"{new_name}.json"
            new_filepath = os.path.join(os.path.dirname(old_filepath), new_filename)
            
            # Save with new name first
            if save_play(new_filepath, play_data):
                # Delete old file only after successful save
                os.remove(old_filepath)
                play_info['filepath'] = new_filepath
                play_info['filename'] = new_filename
                print(f"\nPlay renamed successfully to: {new_filename}")
                return True
            else:
                print("\nFailed to save play with new name")
                return False
                
        except Exception as e:
            print(f"\nError renaming play: {e}")
            return False
    return False

def update_play_class(play_data):
    """Auto-adjust play class based on conditional plays configuration"""
    # Initialize if missing
    if 'conditional_plays' not in play_data:
        play_data['conditional_plays'] = {'OCO_trigger': None, 'OTO_trigger': None}
    
    # Check if this play has any child plays
    has_children = (
        play_data['conditional_plays'].get('OCO_trigger') or 
        play_data['conditional_plays'].get('OTO_trigger')
    )
    
    # Get all plays to check if this play is listed as OTO child
    all_plays = get_all_plays()
    is_oto_child = False
    
    current_filename = os.path.basename(play_data.get('filepath', ''))
    
    for play in all_plays:
        play_data = load_play(play['filepath'])
        if play_data and 'conditional_plays' in play_data:
            if play_data['conditional_plays'].get('OTO_trigger') == current_filename:
                is_oto_child = True
                break
    
    # Set play class based on conditions
    if is_oto_child:
        play_data['play_class'] = 'OTO'
    elif has_children:
        play_data['play_class'] = 'PRIMARY'
    else:
        play_data['play_class'] = 'SIMPLE'

def get_field_value_display(play_data, field):
    """Get formatted display string for field value"""
    if field == "rename_play":
        return play_data.get("play_name", "Not set")
    elif field == "take_profit":
        tp = play_data.get("take_profit", {})
        if "stock_price" in tp:
            return f"${tp['stock_price']:.2f} (stock price)"
        elif "premium_pct" in tp:
            return f"{tp['premium_pct']}% (premium)"
        return "Not set"
    elif field == "stop_loss":
        sl = play_data.get("stop_loss", {})
        if "stock_price" in sl:
            return f"${sl['stock_price']:.2f} (stock price)"
        elif "premium_pct" in sl:
            return f"{sl['premium_pct']}% (premium)"
        return "Not set"
    elif field == "entry_point":
        value = play_data.get(field)
        return f"${value:.2f}" if value is not None else "Not set"
    elif field == "strike_price":
        value = play_data.get(field)
        return f"${float(value):.2f}" if value else "Not set"
    elif field == "conditional_plays (OCO & OTO)":
        cond = play_data.get("conditional_plays", {})
        oco = cond.get("OCO_trigger", "None")
        oto = cond.get("OTO_trigger", "None")
        return f"OCO: {oco}, OTO: {oto}"
    else:
        return str(play_data.get(field, "Not set"))

def edit_specific_play(filename):
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
            "rename_play",
            "symbol",
            "expiration_date", 
            "trade_type",
            "strike_price",
            "entry_point",
            "take_profit",
            "stop_loss",
            "contracts",
            "play_expiration_date",
            "OCO_trigger",
            "OTO_trigger"
        ]
        
        # Find longest field name for alignment
        max_field_len = max(len(field) for field in fields)
        
        # Display fields with current values
        for i, field in enumerate(fields, 1):
            if field in ["OCO_trigger", "OTO_trigger"]:
                value = play_data.get("conditional_plays", {}).get(field, "None")
            else:
                value = get_field_value_display(play_data, field)
            
            dots = "." * (max_field_len - len(field) + 5)
            print(f"{i}. {field}{dots}{value}")
        
        field_selection = get_input(
            "\nEnter the number of the field to edit (0 to save and exit): ",
            type_cast=int,
            validation=lambda x: 0 <= x <= len(fields),
            error_message=f"Please enter a number between 0 and {len(fields)}"
        )

        if field_selection == 0:
            break

        if fields[field_selection - 1] == "rename_play":
            rename_play(play_data, play_info)
        elif fields[field_selection - 1] in ["OCO_trigger", "OTO_trigger"]:
            edit_conditional_plays(play_data, play_info['filepath'])
        else:
            edit_play_field(play_data, fields[field_selection - 1], play_info['filepath'])

    # Save changes
    if save_play(play_info['filepath'], play_data):
        print(f"\nChanges saved to {play_info['filename']}")
    else:
        print("\nError saving changes")

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