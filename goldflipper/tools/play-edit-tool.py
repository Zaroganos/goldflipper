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
    # First check if play is in 'open' folder and field is protected
    protected_fields = ['symbol', 'expiration_date', 'trade_type', 'strike_price', 'entry_point', 'contracts']
    if '/open/' in filepath and field in protected_fields:
        print(f"\nERROR: {get_display_name(field)} cannot be modified for plays in the 'open' folder")
        return
            
    if field == 'symbol':
        confirm = get_input(
            "\nWARNING: Changing the symbol will affect the option contract symbol. DO NOT DO THIS unless you are absolutely sure. Continue? (y/N): ",
            str,
            validation=lambda x: x.lower() in ['y', 'n', ''],
            error_message="Please enter 'y' or 'n'"
        )
        if confirm.lower() != 'y':
            return
            
    if field == 'expiration_date':
        # Only allow editing for plays in 'new' folder
        if not os.path.normpath(filepath).replace(os.sep, '/').split('/plays/')[1].startswith('new/'):
            print("\nERROR: You are attempting to modify the Option Contract Expiration Date. This field should only be modified for a NEW play, in case you wish to change the expiration. If you wish to duplicate this play with a new expiration date, there is an option for that.")
            return
            
        confirm = get_input(
            "\nWARNING: Changing expiration date will affect the option contract symbol. DO NOT DO THIS unless you are absolutely sure you want to change the option's expiration date. Continue? (y/N): ",
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
            new_date = datetime.strptime(new_value, "%m/%d/%Y")
            
            # Get the current contract symbol
            old_contract_symbol = play_data['option_contract_symbol']
            
            # Find where the date portion starts (after the ticker symbol)
            # Look for the first occurrence of the year (24 for 2024)
            year_str = str(new_date.year % 100)  # "24"
            date_start = old_contract_symbol.find(year_str)
            if date_start == -1:
                print("Error: Could not locate date portion in option contract symbol")
                return
            
            # Get the parts of the contract symbol
            symbol_prefix = old_contract_symbol[:date_start]  # Ticker symbol (SPY, F, etc.)
            symbol_suffix = old_contract_symbol[date_start + 6:]  # C00200000 or P00200000
            
            # Create new contract symbol with the new date
            new_date_str = f"{new_date.year % 100}{new_date.month:02d}{new_date.day:02d}"
            new_contract_symbol = f"{symbol_prefix}{new_date_str}{symbol_suffix}"
            
            # Store old filename before updates
            old_filename = os.path.basename(filepath)
            
            # Update both the expiration date and the contract symbol
            play_data['expiration_date'] = new_value
            play_data['option_contract_symbol'] = new_contract_symbol
            
            # Update play name if it contains the old contract symbol
            if 'play_name' in play_data and old_contract_symbol in play_data['play_name']:
                play_data['play_name'] = play_data['play_name'].replace(
                    old_contract_symbol,
                    new_contract_symbol
                )
                
                # Generate new filepath with updated name
                new_filename = f"{play_data['play_name']}.json"
                new_filepath = os.path.join(os.path.dirname(filepath), new_filename)
                
                # Save to new file first
                if save_play(new_filepath, play_data):
                    # Delete old file only after successful save
                    try:
                        os.remove(filepath)
                        print(f"\nFile renamed from {old_filename} to {new_filename}")
                    except Exception as e:
                        print(f"\nError removing old file: {e}")
                        return
                else:
                    print("\nError saving new file")
                    return
            else:
                # If play name wasn't changed, just save to same file
                if not save_play(filepath, play_data):
                    print("\nError saving changes")
                    return
            
            return

    # Play Expiration Date
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
        print("\nSetting Take Profit parameters...")
        tp_price_type = get_price_condition_type()
        
        # Initialize take profit structure
        play_data['take_profit'] = {
            'stock_price': None,
            'stock_price_pct': None,
            'premium_pct': None,
            'order_type': 'market'
        }

        if tp_price_type in [1, 4]:  # Absolute stock price
            price = get_input(
                "Enter take profit stock price: ",
                float,
                validation=lambda x: x > 0,
                error_message="Please enter a valid positive number"
            )
            play_data['take_profit']['stock_price'] = price

        elif tp_price_type == 3:  # Stock price % movement only
            pct = get_input(
                "Enter take profit stock price percentage movement: ",
                float,
                validation=lambda x: x > 0,
                error_message="Please enter a valid positive percentage"
            )
            play_data['take_profit']['stock_price_pct'] = pct

        if tp_price_type in [2, 4, 5]:  # Any condition involving premium %
            premium = get_input(
                "Enter take profit premium percentage: ",
                float,
                validation=lambda x: x > 0,
                error_message="Please enter a valid positive percentage"
            )
            play_data['take_profit']['premium_pct'] = premium

        if tp_price_type == 5:  # Stock price % + premium %
            pct = get_input(
                "Enter take profit stock price percentage movement: ",
                float,
                validation=lambda x: x > 0,
                error_message="Please enter a valid positive percentage"
            )
            play_data['take_profit']['stock_price_pct'] = pct

        # Get order type (using existing functionality)
        play_data['take_profit']['order_type'] = get_input(
            "\nEnter order type (market/limit): ",
            str,
            validation=lambda x: x.lower() in ['market', 'limit'],
            error_message="Please enter 'market' or 'limit'"
        ).lower()

    elif field == 'stop_loss':
        # Get SL type first (using existing functionality)
        sl_type = get_input(
            "\nEnter stop loss type (STOP/LIMIT/CONTINGENCY): ",
            str,
            validation=lambda x: x.upper() in ['STOP', 'LIMIT', 'CONTINGENCY'],
            error_message="Please enter STOP, LIMIT, or CONTINGENCY"
        ).upper()

        price_type = get_price_condition_type()

        # Initialize stop loss structure
        play_data['stop_loss'] = {
            'SL_type': sl_type,
            'stock_price': None,
            'stock_price_pct': None,
            'premium_pct': None,
            'contingency_stock_price': None,
            'contingency_stock_price_pct': None,
            'contingency_premium_pct': None,
            'order_type': None
        }

        if sl_type in ['STOP', 'LIMIT']:
            if price_type in [1, 4]:  # Absolute stock price
                price = get_input(
                    "Enter stop loss stock price: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive number"
                )
                play_data['stop_loss']['stock_price'] = price

            elif price_type == 3:  # Stock price % movement only
                pct = get_input(
                    "Enter stop loss stock price percentage movement: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive percentage"
                )
                play_data['stop_loss']['stock_price_pct'] = pct

            if price_type in [2, 4, 5]:  # Premium % conditions
                premium = get_input(
                    "Enter stop loss premium percentage: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive percentage"
                )
                play_data['stop_loss']['premium_pct'] = premium

            if price_type == 5:  # Stock price % + premium %
                pct = get_input(
                    "Enter stop loss stock price percentage movement: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive percentage"
                )
                play_data['stop_loss']['stock_price_pct'] = pct

        else:  # CONTINGENCY type
            # Main conditions
            if price_type in [1, 4]:  # Absolute stock price
                main_price = get_input(
                    "Enter main stop loss stock price: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive number"
                )
                backup_price = get_input(
                    "Enter backup stop loss stock price: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive number"
                )
                play_data['stop_loss']['stock_price'] = main_price
                play_data['stop_loss']['contingency_stock_price'] = backup_price

            elif price_type == 3:  # Stock price % movement only
                main_pct = get_input(
                    "Enter main stop loss stock price percentage movement: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive percentage"
                )
                backup_pct = get_input(
                    "Enter backup stop loss stock price percentage movement: ",
                    float,
                    validation=lambda x: x > main_pct,
                    error_message="Backup percentage must be higher than main percentage"
                )
                play_data['stop_loss']['stock_price_pct'] = main_pct
                play_data['stop_loss']['contingency_stock_price_pct'] = backup_pct

            if price_type in [2, 4, 5]:  # Premium % conditions
                main_premium = get_input(
                    "Enter main stop loss premium percentage: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive percentage"
                )
                backup_premium = get_input(
                    "Enter backup stop loss premium percentage: ",
                    float,
                    validation=lambda x: x > main_premium,
                    error_message="Backup percentage must be higher than main percentage"
                )
                play_data['stop_loss']['premium_pct'] = main_premium
                play_data['stop_loss']['contingency_premium_pct'] = backup_premium

            if price_type == 5:  # Stock price % + premium %
                main_pct = get_input(
                    "Enter main stop loss stock price percentage movement: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive percentage"
                )
                backup_pct = get_input(
                    "Enter backup stop loss stock price percentage movement: ",
                    float,
                    validation=lambda x: x > main_pct,
                    error_message="Backup percentage must be higher than main percentage"
                )
                play_data['stop_loss']['stock_price_pct'] = main_pct
                play_data['stop_loss']['contingency_stock_price_pct'] = backup_pct

        # Set order type(s) based on SL_type (using existing functionality)
        if sl_type == 'STOP':
            play_data['stop_loss']['order_type'] = 'market'
        elif sl_type == 'LIMIT':
            play_data['stop_loss']['order_type'] = get_input(
                "\nEnter order type (limit/stop_limit): ",
                str,
                validation=lambda x: x.lower() in ['limit', 'stop_limit'],
                error_message="Please enter 'limit' or 'stop_limit'"
            ).lower()
        else:  # CONTINGENCY
            play_data['stop_loss']['order_type'] = ['limit', 'market']

    elif field == 'contracts':
        # Only allow editing for plays in 'new' folder
        if not os.path.normpath(filepath).replace(os.sep, '/').split('/plays/')[1].startswith('new/'):
            print("\nERROR: Number of contracts can only be modified for NEW plays")
            return
            
        new_value = get_input(
            "Enter number of contracts: ",
            int,
            validation=lambda x: x > 0,
            error_message="Please enter a positive number"
        )
        if new_value is not None:
            play_data['contracts'] = new_value

    elif field == 'conditional_plays':
        edit_conditional_plays(play_data, filepath)
        return

    # current_value = play_data.get(field, "Not set")
    # print(f"\nCurrent value of {field}: {current_value}")

    if field == 'symbol':
        # Only allow editing for plays not in 'open' folder
        if '/open/' in filepath:
            print("\nERROR: Symbol can only be modified for plays not in the 'open' folder")
            return
            
        confirm = get_input(
            "\nWARNING: Changing the symbol will affect the option contract symbol. DO NOT DO THIS unless you are absolutely sure. Continue? (y/N): ",
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
            # Store old values before updates
            old_symbol = play_data['symbol']
            old_contract_symbol = play_data['option_contract_symbol']
            old_filename = os.path.basename(filepath)
            
            # Update symbol and option contract symbol
            play_data['symbol'] = new_value
            play_data['option_contract_symbol'] = play_data['option_contract_symbol'].replace(
                old_symbol, new_value
            )
            
            # Update play name if it contains the old contract symbol
            if 'play_name' in play_data and old_contract_symbol in play_data['play_name']:
                play_data['play_name'] = play_data['play_name'].replace(
                    old_contract_symbol,
                    play_data['option_contract_symbol']
                )
                
                # Generate new filepath with updated name
                new_filename = f"{play_data['play_name']}.json"
                new_filepath = os.path.join(os.path.dirname(filepath), new_filename)
                
                # Save to new file first
                if save_play(new_filepath, play_data):
                    # Delete old file only after successful save
                    try:
                        os.remove(filepath)
                        print(f"\nFile renamed from {old_filename} to {new_filename}")
                    except Exception as e:
                        print(f"\nError removing old file: {e}")
                        return
                else:
                    print("\nError saving new file")
                    return
            else:
                # If play name wasn't changed, just save to same file
                if not save_play(filepath, play_data):
                    print("\nError saving changes")
                    return
            
            return

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
            play_data['entry_point']['stock_price'] = new_value

    elif field == 'strike_price':
        new_value = get_input(
            "Enter the strike price: ",
            float,
            error_message="Please enter a valid number for the strike price."
        )
        if new_value is not None:
            play_data['strike_price'] = str(new_value)  # Store as string like in creation tool

 #   else:
 #       new_value = get_input(
 #           f"Enter new value for {field} (press Enter to keep current): ",
 #           optional=True
 #        )
 #       if new_value is not None:
 #           play_data[field] = new_value


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
    # Initialize conditional_plays if it doesn't exist
    if 'conditional_plays' not in play_data:
        play_data['conditional_plays'] = {'OCO_trigger': None, 'OTO_trigger': None}
        
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
    # Initialize conditional_plays if it doesn't exist
    if 'conditional_plays' not in play_data:
        play_data['conditional_plays'] = {'OCO_trigger': None, 'OTO_trigger': None}
        
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
    """Get formatted display value for a field"""
    if field == "play_name":
        return play_data.get("play_name", "Not set")
    elif field == "symbol":
        return play_data.get("symbol", "Not set")
    elif field == "strike_price":
        return f"${float(play_data.get('strike_price', 0)):.2f}"
    elif field == "entry_point":
        entry_point = play_data.get('entry_point', {})
        if isinstance(entry_point, dict):
            stock_price = entry_point.get('stock_price')
            return f"${float(stock_price):.2f}" if stock_price is not None else "Not set"
        return "Not set"
    elif field == "take_profit":
        tp_data = play_data.get('take_profit', {})
        displays = []
        
        if tp_data.get('stock_price') is not None:
            displays.append(f"Stock: ${float(tp_data['stock_price']):.2f}")
        if tp_data.get('stock_price_pct') is not None:
            displays.append(f"Stock%: {float(tp_data['stock_price_pct'])}%")
        if tp_data.get('premium_pct') is not None:
            displays.append(f"Prem%: {float(tp_data['premium_pct'])}%")
            
        return " + ".join(displays) if displays else "Not set"
        
    elif field == "stop_loss":
        sl_data = play_data.get('stop_loss', {})
        displays = []
        
        # Main conditions
        main_conditions = []
        if sl_data.get('stock_price') is not None:
            main_conditions.append(f"Stock: ${float(sl_data['stock_price']):.2f}")
        if sl_data.get('stock_price_pct') is not None:
            main_conditions.append(f"Stock%: {float(sl_data['stock_price_pct'])}%")
        if sl_data.get('premium_pct') is not None:
            main_conditions.append(f"Prem%: {float(sl_data['premium_pct'])}%")
        
        if main_conditions:
            displays.append("Main(" + " + ".join(main_conditions) + ")")
            
        # Contingency conditions if applicable
        if sl_data.get('SL_type') == 'CONTINGENCY':
            backup_conditions = []
            if sl_data.get('contingency_stock_price') is not None:
                backup_conditions.append(f"Stock: ${float(sl_data['contingency_stock_price']):.2f}")
            if sl_data.get('contingency_stock_price_pct') is not None:
                backup_conditions.append(f"Stock%: {float(sl_data['contingency_stock_price_pct'])}%")
            if sl_data.get('contingency_premium_pct') is not None:
                backup_conditions.append(f"Prem%: {float(sl_data['contingency_premium_pct'])}%")
            
            if backup_conditions:
                displays.append("Backup(" + " + ".join(backup_conditions) + ")")
        
        return " | ".join(displays) if displays else "Not set"
    elif field == 'OCO_trigger':
        return play_data.get('conditional_plays', {}).get('OCO_trigger') or 'Not set'
    elif field == 'OTO_trigger':
        return play_data.get('conditional_plays', {}).get('OTO_trigger') or 'Not set'
    else:
        return str(play_data.get(field, "Not set"))

def get_display_name(field):
    """Convert field names to nice display format"""
    display_names = {
        "play_name": "Rename Play",
        "symbol": "Symbol",
        "expiration_date": "Expiration Date",
        "trade_type": "Trade Type",
        "strike_price": "Strike Price",
        "entry_point": "Entry Point",
        "take_profit": "Take Profit",
        "stop_loss": "Stop Loss",
        "contracts": "Contracts",
        "play_expiration_date": "Play Expiration Date",
        "OCO_trigger": "OCO Trigger",
        "OTO_trigger": "OTO Trigger"
    }
    return display_names.get(field, field)

def edit_specific_play(filename):
    play_info = find_play_file(filename)
    if not play_info:
        print(f"Error: Play file '{filename}' not found")
        return
    
    print(f"\nEditing play: [{play_info['folder']}] {play_info['filename']}")
    play_data = load_play(play_info['filepath'])
    if not play_data:
        return

    # Define protected fields and check folder
    protected_fields = ['symbol', 'expiration_date', 'trade_type', 'strike_price', 'entry_point', 'contracts']
    is_open_play = play_info['folder'] == 'open'

    while True:
        print("\nEditable Fields:")
        fields = [
            "play_name",
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
        
        # Display fields with current values and track valid options
        valid_options = []
        for i, field in enumerate(fields, 1):
            number_padding = 1 if i <10 else 0
            value = get_field_value_display(play_data, field)
            display_name = get_display_name(field)
            dots = "." * (30 - len(display_name) + number_padding)
            
            if is_open_play and field in protected_fields:
                print(f"{i}. {display_name}{dots}{value} (locked)")
            else:
                print(f"{i}. {display_name}{dots}{value}")
                valid_options.append(i)
        
        # Add additional options
        print("\nAdditional Options:")
        print(f"{len(fields) + 1}. Duplicate Play")
        print(f"{len(fields) + 2}. Delete Play")
        valid_options.extend([len(fields) + 1, len(fields) + 2])
        
        # Get user selection
        field_selection = get_input(
            "\nEnter the number of the field to edit or option to perform (0 to save and exit): ",
            type_cast=int,
            validation=lambda x: 0 <= x <= len(fields) + 2,
            error_message=f"Please enter a number between 0 and {len(fields) + 2}"
        )

        if field_selection == 0:
            break

        elif field_selection == 13:
            duplicate_play(play_data, play_info['filepath'])
        elif field_selection == 14:
            delete_play(play_data, play_info['filepath'])
            return
        elif field_selection == 1:
            play_name(play_data, play_info)
        elif field_selection in valid_options:
            field = fields[field_selection - 1]
            if is_open_play and field in protected_fields:
                print(f"\nERROR: Cannot modify {get_display_name(field)} for plays in the 'open' folder")
                continue
                
            # Special handling for OCO and OTO triggers
            if field == "OCO_trigger":
                edit_oco_trigger(play_data, play_info['filepath'])
            elif field == "OTO_trigger":
                edit_oto_trigger(play_data, play_info['filepath'])
            else:
                edit_play_field(play_data, field, play_info['filepath'])

    # Save changes
    if save_play(play_info['filepath'], play_data):
        print(f"\nChanges saved to {play_info['filename']}")
    else:
        print("\nError saving changes")

def duplicate_play(play_data, original_filepath):
    """Duplicate a play with optional modifications"""
    print("\n=== Duplicate Play ===")
    
    # Choose destination folder
    print("\nSelect destination folder:")
    print("1. New")
    print("2. Temp (if OTO)")
    
    folder_choice = get_input(
        "Enter choice (1-2): ",
        int,
        validation=lambda x: x in [1, 2],
        error_message="Please enter 1 or 2"
    )
    
    destination_folder = 'new' if folder_choice == 1 else 'temp'
    
    # Create a deep copy of the play data
    new_play_data = json.loads(json.dumps(play_data))
    
    # Generate new timestamp for the name
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    new_play_data['play_name'] = f"{new_play_data['option_contract_symbol']}_{timestamp}"
    
    # Set creation date to today
    new_play_data['creation_date'] = datetime.now().strftime('%m/%d/%Y')
    
    # Generate the new filepath
    base_dir = os.path.join(os.path.dirname(original_filepath), '..', destination_folder)
    os.makedirs(base_dir, exist_ok=True)
    new_filepath = os.path.join(base_dir, f"{new_play_data['play_name']}.json")
    
    # Save the duplicated play
    if save_play(new_filepath, new_play_data):
        print(f"\nPlay duplicated successfully to: {destination_folder}/{os.path.basename(new_filepath)}")
        return True
    else:
        print("\nError duplicating play")
        return False

def delete_play(play_data, filepath):
    """Mark a play as deleted and move it to the OLD folder"""
    confirm = get_input(
        "\nAre you sure you want to delete (archive) this play? (y/N): ",
        str,
        validation=lambda x: x.lower() in ['y', 'n', ''],
        error_message="Please enter 'y' or 'n'"
    )
    
    if confirm.lower() != 'y':
        return False
    
    # Add deletion marker
    play_data['DELETED_by_user'] = datetime.now().strftime('%m/%d/%Y %H:%M:%S')
    
    # Create Old folder if it doesn't exist
    old_dir = os.path.join(os.path.dirname(filepath), '..', 'old')
    os.makedirs(old_dir, exist_ok=True)
    
    # Move to Old folder
    old_filepath = os.path.join(old_dir, os.path.basename(filepath))
    
    try:
        # First save to old folder
        if save_play(old_filepath, play_data):
            # Then remove original file
            os.remove(filepath)
            print(f"\nPlay moved to old folder and marked as deleted")
            return True
        else:
            print("\nError saving to old folder")
            return False
    except Exception as e:
        print(f"\nError during deletion: {e}")
        return False

def play_name(play_data, play_info):
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

def edit_play():
    """Main function to edit plays"""
    plays = get_all_plays()
    if not plays:
        print("No plays found")
        return

    print("\nAvailable Plays:")
    for i, play in enumerate(plays, 1):
        print(f"{i}. [{play['folder']}] {play['filename']}")

    selection = get_input(
        "\nEnter the number of the play to edit (0 to exit): ",
        type_cast=int,
        validation=lambda x: 0 <= x <= len(plays),
        error_message=f"Please enter a number between 0 and {len(plays)}"
    )

    if selection == 0:
        return

    selected_play = plays[selection - 1]
    edit_specific_play(selected_play['filename'])

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

def get_price_condition_type():
    """Get user's choice for price condition type."""
    print("\nSelect price condition type:")
    print("1. Stock price only (absolute value)")
    print("2. Option premium % only")
    print("3. Stock price % movement only")
    print("4. Both stock price (absolute) AND option premium %")
    print("5. Both stock price % movement AND option premium %")
    
    return get_input(
        "Choice (1-5): ",
        int,
        validation=lambda x: x in [1, 2, 3, 4, 5],
        error_message="Please enter a number between 1 and 5"
    )

if __name__ == "__main__":
    main()