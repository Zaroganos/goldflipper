import os
import json
import re
from datetime import datetime
import platform
import subprocess
import yaml

def get_input(prompt, input_type=str, validation=None, error_message="Invalid input. Please try again.", optional=False):
    """
    Helper function to get validated input from the user.

    Parameters:
    - prompt (str): The message to show the user.
    - input_type (type): The type to convert the input into (e.g., int, float, str).
    - validation (function): A function that takes the input and returns True if valid, False otherwise.
    - error_message (str): The message to show if validation fails.
    - optional (bool): If True, allows the user to skip input by entering nothing.

    Returns:
    - The validated input converted to input_type, or None if optional and skipped.
    """
    while True:
        user_input = input(prompt).strip()
        if optional and user_input == "":
            return None
        try:
            converted_input = input_type(user_input)
            if validation and not validation(converted_input):
                print(error_message)
            else:
                return converted_input
        except ValueError:
            print(error_message)

def validate_choice(choice, options):
    """
    Validates if the user's choice is within the allowed options.

    Parameters:
    - choice (str): The user's choice.
    - options (list): The list of allowed options.

    Returns:
    - bool: True if valid, False otherwise.
    """
    return choice.upper() in options

def sanitize_filename(name):
    """
    Sanitize the filename by removing or replacing invalid characters.

    Parameters:
    - name (str): The original filename.

    Returns:
    - str: The sanitized filename.
    """
    # Remove any character that is not alphanumeric, underscore, or hyphen
    sanitized = re.sub(r'[^\w\-]', '_', name)
    return sanitized

def create_option_contract_symbol(symbol, expiration_date, strike_price, trade_type):
    """
    Generate the option contract symbol based on user inputs.
    Format: {SYMBOL}{YYMMDD}{C/P}{STRIKE_PRICE_PADDED}
    Example: SPY240621P00550000 (for $550.00 strike price)
    """
    try:
        # Parse and format the expiration date
        exp_date = datetime.strptime(expiration_date, "%m/%d/%Y")
        formatted_date = exp_date.strftime("%y%m%d")
    except ValueError:
        raise ValueError("Invalid expiration date format. Please use MM/DD/YYYY.")

    # Determine the option type (Call or Put)
    option_type = "C" if trade_type.upper() == "CALL" else "P"

    try:
        # Convert strike price to tenths of cents by multiplying by 1000
        strike_tenths_cents = int(round(float(strike_price) * 1000))
    except ValueError:
        raise ValueError("Invalid strike price. Please enter a numeric value.")

    # Format as an 8-digit number with leading zeros
    padded_strike = f"{strike_tenths_cents:08d}"

    # Assemble the final option contract symbol
    final_symbol = f"{symbol.upper()}{formatted_date}{option_type}{padded_strike}"

    return final_symbol

def get_price_condition_type():
    """Get user's choice for price condition type."""
    print("\nSelect price condition type(s):")
    print("1. Stock price (absolute value)")
    print("2. Option premium %")
    print("3. Stock price % movement")
    print("Enter your choices (separated by space, comma, or dash). Examples: '1 2 3' or '1,2' or '1-3'")
    
    while True:
        user_input = get_input(
            "Choice(s): ",
            str,
            validation=lambda x: True,  # We'll validate the parsed result
            error_message="Invalid input format."
        ).strip()
        
        # Parse the input
        try:
            choices = set()
            # Split by comma first, then handle each part
            for part in user_input.replace(' ', ',').split(','):
                if '-' in part:
                    # Handle range (e.g., "1-3")
                    start, end = map(int, part.split('-'))
                    choices.update(range(start, end + 1))
                elif part:  # Skip empty parts
                    choices.add(int(part))
            
            # Validate choices
            if not choices:
                print("Please select at least one option.")
                continue
                
            if not all(1 <= choice <= 3 for choice in choices):
                print("Choices must be between 1 and 3.")
                continue
                
            return sorted(list(choices))  # Return sorted list of unique choices
            
        except ValueError:
            print("Invalid input format. Please use numbers 1-3 separated by space, comma, or dash.")
            continue

def get_premium_percentage():
    """Get premium percentage from user."""
    return get_input(
        "Enter the premium percentage: ",
        float,
        validation=lambda x: 0 < x <= 100,
        error_message="Please enter a percentage between 0 and 100. If you want a higher %, ask iliya to code it in."
    )

def get_order_type_choice(is_stop_loss=False, transaction_type=""):
    """Get user's choice for order type (market/limit).
    
    Args:
        is_stop_loss (bool): If True, adds warning about market orders being safer for SL
        transaction_type (str): The type of transaction (Entry, Take Profit, Stop Loss)
    """
    prompt = f"\nSelect order type for {transaction_type}:"
    prompt += "\n1. Market order"
    prompt += "\n2. Limit order (default)"
    prompt += "\nChoice (1/2) [2]: "
    
    choice = get_input(
        prompt,
        int,
        validation=lambda x: x in [1, 2],
        error_message="Please enter 1 for market or 2 for limit order.",
        optional=True
    )
    
    # If optional input is skipped (None returned), default to 2 (limit)
    return 'market' if choice == 1 else 'limit'

def get_sl_type_choice():
    """Get user's choice for stop loss execution type (STOP/LIMIT/CONTINGENCY)."""
    print("\nSelect Stop Loss Type:")
    print("1. Stop (market order when price is hit)")
    print("2. Limit (limit order when price is hit)")
    print("3. Contingency (primary limit order with backup market order at a worse price)")
    
    return get_input(
        "Choice (1/2/3): ",
        int,
        validation=lambda x: x in [1, 2, 3],
        error_message="Please enter 1 for 'Stop' (Market Order), 2 for 'Limit' (Limit Order), or 3 for 'Contingency' (Primary Limit Order with backup Market Order)."
    )

def validate_contingency_prices(main_price, backup_price, is_stock_price, trade_type):
    """
    Validate that the backup price is worse than the main price.
    
    Args:
        main_price (float): Primary stop loss price
        backup_price (float): Backup/safety stop loss price
        is_stock_price (bool): True if validating stock prices, False for premium percentages
        trade_type (str): 'CALL' or 'PUT'
    
    Returns:
        bool: True if valid, False if invalid
    """
    if is_stock_price:
        if trade_type == 'CALL':
            return backup_price < main_price  # Lower stock price is worse for calls
        else:  # PUT
            return backup_price > main_price  # Higher stock price is worse for puts
    else:  # Premium percentage
        return backup_price > main_price  # Higher percentage means bigger loss

def get_multiple_tp_choice():
    """Get user's choice for using multiple take profits."""
    return get_input(
        "\nWould you like to set multiple Take Profit levels? (Y/N): ",
        str,
        validation=lambda x: x.upper() in ['Y', 'N'],
        error_message="Please enter Y or N."
    ).upper() == 'Y'

def get_number_of_tps():
    """Get the number of take profit levels desired."""
    return get_input(
        "\nHow many Take Profit levels would you like to set? (2-5): ",
        int,
        validation=lambda x: 2 <= x <= 5,
        error_message="Please enter a number between 2 and 5."
    )

def get_tp_parameters(tp_number=None, total_tps=None):
    """Get take profit parameters from user.
    
    Args:
        tp_number (int, optional): The current TP number (for multiple TPs)
        total_tps (int, optional): Total number of TPs being created
    
    Returns:
        dict: Take profit parameters
    """
    tp_data = {
        'stock_price': None,
        'stock_price_pct': None,
        'premium_pct': None,
        'order_type': 'market'
    }

    if tp_number is not None:
        print(f"\nSetting Take Profit #{tp_number} of {total_tps}")
        tp_data['TP_number'] = tp_number
        tp_data['total_TPs'] = total_tps

    tp_price_types = get_price_condition_type()

    if 1 in tp_price_types:  # Absolute stock price
        tp_stock_price = get_input(
            f"Enter take profit stock price{f' #{tp_number}' if tp_number else ''}: ",
            float,
            validation=lambda x: x > 0,
            error_message="Please enter a valid positive number for the take profit stock price."
        )
        tp_data['stock_price'] = tp_stock_price

    if 3 in tp_price_types:  # Stock price % movement
        tp_stock_price_pct = get_input(
            f"Enter take profit stock price percentage movement{f' #{tp_number}' if tp_number else ''}: ",
            float,
            validation=lambda x: x > 0,
            error_message="Please enter a valid positive percentage"
        )
        tp_data['stock_price_pct'] = tp_stock_price_pct

    if 2 in tp_price_types:  # Option premium %
        tp_premium_pct = get_premium_percentage()
        tp_data['premium_pct'] = tp_premium_pct

    # Take profit order type
    tp_data['order_type'] = get_order_type_choice(
        transaction_type=f"Take Profit{f' #{tp_number}' if tp_number else ''}"
    )

    return tp_data

def create_play():
    """
    Interactive tool to create a play for options trading, following the minimal template.
    """
    while True:
        play = {}

        play['symbol'] = get_input(
            "Enter the ticker symbol (e.g., SPY): ",
            str,
            validation=lambda x: len(x) > 0,
            error_message="Ticker symbol cannot be empty."
        ).upper()

        play['trade_type'] = get_input(
            "Enter the trade type (CALL or PUT): ",
            str,
            validation=lambda x: validate_choice(x, ["CALL", "PUT"]),
            error_message="Invalid trade type. Please enter 'CALL' or 'PUT'."
        ).upper()

        # Entry point setup
        play['entry_point'] = {}
        play['entry_point']['stock_price'] = get_input(
            "Enter the entry stock price: ",
            float,
            error_message="Please enter a valid number for the entry price."
        )
        play['entry_point']['order_type'] = get_order_type_choice(transaction_type="Entry")

        # Save strike price as a string
        play['strike_price'] = str(get_input(
            "Enter the strike price: ",
            float,
            error_message="Please enter a valid number for the strike price."
        ))

        play['expiration_date'] = get_input(
            "Enter the option contract expiration date (MM/DD/YYYY): ",
            str,
            validation=lambda x: datetime.strptime(x, "%m/%d/%Y"),
            error_message="Please enter a valid date in MM/DD/YYYY format."
        )

        play['contracts'] = get_input(
            "Enter the number of contracts: ",
            int,
            validation=lambda x: x > 0,
            error_message="Please enter a positive integer for the number of contracts."
        )

        # Prompt for an optional play name
        play_name_input = get_input(
            "Enter the play's name (optional, press Enter to skip): ",
            str,
            validation=lambda x: True,  # No specific validation
            error_message="Invalid input.",
            optional=True
        )

        # Automatically generate the option contract symbol
        try:
            play['option_contract_symbol'] = create_option_contract_symbol(
                play['symbol'],
                play['expiration_date'],
                play['strike_price'],
                play['trade_type']
            )
            print(f"Generated option contract symbol: {play['option_contract_symbol']}")
        except ValueError as ve:
            print(f"Error generating option contract symbol: {ve}")
            return  # Exit the function if there's an error

        # Determine the play's name
        if play_name_input:
            play['play_name'] = play_name_input
            filename = sanitize_filename(play['play_name']) + ".json"
        else:
            system_time = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_name = f"{play['option_contract_symbol']}_{system_time}"
            play['play_name'] = default_name
            filename = default_name + ".json"

        # Take profit section
        print("\nSetting Take Profit parameters...")
        
        # Load settings to check if multiple TPs are enabled
        settings_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
        with open(settings_path, 'r') as f:
            settings = yaml.safe_load(f)
        
        multiple_tps_enabled = settings.get('options_swings', {}).get('Take_Profit', {}).get('multiple_TPs', False)
        
        if multiple_tps_enabled and get_multiple_tp_choice():
            num_tps = get_number_of_tps()
            base_play = play.copy()  # Store our base play data
            plays_to_create = []

            # Get stop loss parameters first (will be same for all plays)
            print("\nSetting Stop Loss parameters (will apply to all Take Profit levels)...")
            sl_price_types = get_price_condition_type()
            base_play['stop_loss'] = {
                'SL_type': None,
                'stock_price': None,
                'stock_price_pct': None,
                'premium_pct': None,
                'contingency_stock_price': None,
                'contingency_stock_price_pct': None,
                'contingency_premium_pct': None,
                'order_type': None,
                'SL_option_prem': None,
                'SL_stock_price_target': None,
                'contingency_SL_stock_price_target': None
            }
            
            # Get all the stop loss parameters using existing logic
            sl_type_choice = get_sl_type_choice()
            base_play['stop_loss']['SL_type'] = (
                'STOP' if sl_type_choice == 1 else
                'LIMIT' if sl_type_choice == 2 else
                'CONTINGENCY'
            )

            # Create each play with its own TP
            for i in range(num_tps):
                current_play = base_play.copy()
                current_play['take_profit'] = get_tp_parameters(i + 1, num_tps)
                current_play['play_name'] = f"{base_play['play_name']}_{i+1}"
                plays_to_create.append(current_play)
        else:
            # Single TP using the same function
            play['take_profit'] = get_tp_parameters()

        # Stop loss section
        print("\nSetting Stop Loss parameters...")
        sl_price_types = get_price_condition_type()
        play['stop_loss'] = {
            'SL_type': None,
            'stock_price': None,
            'stock_price_pct': None,
            'premium_pct': None,
            'contingency_stock_price': None,
            'contingency_stock_price_pct': None,
            'contingency_premium_pct': None,
            'order_type': None,
            'SL_option_prem': None,
            'SL_stock_price_target': None,
            'contingency_SL_stock_price_target': None
        }

        # Get SL type first as it affects how many conditions we need
        sl_type_choice = get_sl_type_choice()
        play['stop_loss']['SL_type'] = (
            'STOP' if sl_type_choice == 1 else
            'LIMIT' if sl_type_choice == 2 else
            'CONTINGENCY'
        )

        if play['stop_loss']['SL_type'] in ['STOP', 'LIMIT']:
            # Single set of conditions
            if 1 in sl_price_types:  # Absolute stock price
                sl_stock_price = get_input(
                    "Enter stop loss stock price: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive number for the stop loss stock price."
                )
                play['stop_loss']['stock_price'] = sl_stock_price

            if 3 in sl_price_types:  # Stock price % movement
                sl_stock_price_pct = get_input(
                    "Enter stop loss stock price percentage movement: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive percentage"
                )
                play['stop_loss']['stock_price_pct'] = sl_stock_price_pct

            if 2 in sl_price_types:  # Option premium %
                sl_premium_pct = get_premium_percentage()
                play['stop_loss']['premium_pct'] = sl_premium_pct

        else:  # CONTINGENCY type needs two sets of conditions
            if 1 in sl_price_types:  # Absolute stock price
                print("\nEnter main stop loss conditions:")
                main_stock_price = get_input(
                    "Enter main stop loss stock price: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive number for the main stop loss stock price."
                )
                
                while True:
                    print("\nEnter backup/safety stop loss conditions (must be worse than main price):")
                    backup_stock_price = get_input(
                        f"Enter backup stop loss stock price ({'lower' if play['trade_type'] == 'CALL' else 'higher'} than {main_stock_price}): ",
                        float,
                        validation=lambda x: x > 0,
                        error_message="Please enter a valid positive number for the backup stop loss stock price."
                    )
                    
                    if validate_contingency_prices(main_stock_price, backup_stock_price, True, play['trade_type']):
                        break
                    print(f"Error: Backup price must be {'lower' if play['trade_type'] == 'CALL' else 'higher'} than the main price ({main_stock_price}) for a {play['trade_type']}")
                
                play['stop_loss']['stock_price'] = main_stock_price
                play['stop_loss']['contingency_stock_price'] = backup_stock_price

            if 3 in sl_price_types:  # Stock price % movement
                print("\nEnter main stop loss conditions:")
                main_stock_price_pct = get_input(
                    "Enter main stop loss stock price percentage movement: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive percentage"
                )
                
                while True:
                    print("\nEnter backup/safety stop loss conditions (must represent a bigger movement):")
                    backup_stock_price_pct = get_input(
                        "Enter backup stop loss stock price percentage movement (must be higher than main %): ",
                        float,
                        validation=lambda x: x > main_stock_price_pct,
                        error_message=f"Please enter a percentage higher than {main_stock_price_pct}%"
                    )
                    
                    if backup_stock_price_pct > main_stock_price_pct:
                        break
                    print(f"Error: Backup percentage ({backup_stock_price_pct}%) must be higher than main percentage ({main_stock_price_pct}%)")
                
                play['stop_loss']['stock_price_pct'] = main_stock_price_pct
                play['stop_loss']['contingency_stock_price_pct'] = backup_stock_price_pct

            if 2 in sl_price_types:  # Option premium %
                print("\nEnter main stop loss conditions:") if len(sl_price_types) == 1 else None
                main_premium = get_premium_percentage()
                
                while True:
                    print("\nEnter backup/safety stop loss conditions (must represent a bigger loss):")
                    print(f"Current main stop loss is at {main_premium}% loss from entry")
                    print(f"Backup must be higher than {main_premium}% (representing a bigger loss)")
                    backup_premium = get_premium_percentage()
                    
                    if validate_contingency_prices(main_premium, backup_premium, False, play['trade_type']):
                        break
                    print(f"Error: Backup loss percentage ({backup_premium}%) must be higher than main loss percentage ({main_premium}%) to represent a bigger loss")
                
                play['stop_loss']['premium_pct'] = main_premium
                play['stop_loss']['contingency_premium_pct'] = backup_premium

        # Set order type(s) based on SL_type
        if play['stop_loss']['SL_type'] == 'STOP':
            play['stop_loss']['order_type'] = 'market'
        elif play['stop_loss']['SL_type'] == 'LIMIT':
            play['stop_loss']['order_type'] = get_order_type_choice(
                is_stop_loss=True, 
                transaction_type="Stop Loss"
            )
        else:  # CONTINGENCY
            play['stop_loss']['order_type'] = ['limit', 'market']  # Always this combination for contingency

        play['play_expiration_date'] = get_input(
            f"Enter the play's expiration date (MM/DD/YYYY), or press Enter to make it {play['expiration_date']} by default.): ",
            str,
            optional=True  # Allow the user to skip input
        )
        # Set default to previously entered expiration_date if no input is provided
        if not play['play_expiration_date']:
            play['play_expiration_date'] = play['expiration_date']
        else:
            # Validate the new input
            datetime.strptime(play['play_expiration_date'], "%m/%d/%Y")  # This will raise an error if invalid

        # CONSIDER CHANGING THIS...
        play['play_class'] = (get_input(
            "Enter the conditional play class (PRIMARY, or --> OCO or OTO), or press Enter for Simple: ",
            str,
            validation=lambda x: validate_choice(x, [True, "PRIMARY", "OCO", "OTO"]),
            error_message="Invalid play class. Please press Enter or enter 'PRIMARY', 'OCO', or 'OTO'.",
            optional=True
        ) or "Simple").upper()  #Simple by default
        
        if play['play_class'] == 'PRIMARY':
            # Prompt user to choose an existing play from "new" or "temp" folders
            existing_play = get_input(
                "Link a conditional play to this primary play. Choose an existing play from ['new' if OCO], or ['temp' if OTO], folders (provide the full play name, including the .json extension. Hint: view current plays): ",
                str,
                validation=lambda x: os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'plays', 'new', x)) or 
                                    os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'plays', 'temp', x)),
                error_message="Play not found in 'new' or 'OTO' folders."
            )

            # Check which folder the play is in and set the appropriate field
            if os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'plays', 'new', existing_play)):
                play['conditional_plays'] = {'OCO_trigger': existing_play}
            elif os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'plays', 'temp', existing_play)):
                play['conditional_plays'] = {'OTO_trigger': existing_play}

        play['strategy'] = (
            'Option Swings' if play['play_class'] == 'SIMPLE' else
            'Branching Brackets Option Swings'
        )

        play['creation_date'] = datetime.now().strftime('%Y-%m-%d')  # Automatically populate play's creation date

        play['creator'] = 'user'

        # Update the plays directory path and add status field
        if play['play_class'] == 'OTO':
            plays_dir = os.path.join(os.path.dirname(__file__), '..', 'plays', 'temp')
            play_status = 'TEMP'
        else:
            plays_dir = os.path.join(os.path.dirname(__file__), '..', 'plays', 'new')
            play_status = 'NEW'

        play['status'] = {
            "play_status": play_status,
            "order_id": None,
            "order_status": None,
            "position_exists": False,
            "last_checked": None,
            "closing_order_id": None,
            "closing_order_status": None,
            "contingency_order_id": None,
            "contingency_order_status": None,
            "conditionals_handled": False
        }

        os.makedirs(plays_dir, exist_ok=True)

        filepath = os.path.join(plays_dir, filename)
        with open(filepath, 'w') as f:
            json.dump(play, f, indent=4)

        print(f"Play saved to {filepath}")

        # Open the file in text editor
        try:
            if platform.system() == "Windows":
                subprocess.run(["notepad.exe", filepath])
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", "-t", filepath])
            else:  # Linux
                subprocess.run(["xdg-open", filepath])
            print("Opening play file in text editor...")
        except Exception as e:
            print(f"Could not open file automatically: {e}")

        

        # Ask the user if they want to create another play
        another_play = get_input(
            "Do you want to create another play? (Y/N): ",
            str,
            validation=lambda x: x.upper() in ["Y", "N"],
            error_message="Please enter 'Y' or 'N'."
        ).upper()

        if another_play == "Y":
            os.system('cls' if platform.system() == "Windows" else 'clear')  # Clear the screen
            continue  # Continue to create another play
        else:
            print("Exiting the play creation tool.")
            break  # Exit the loop if the user does not want to create another play

if __name__ == "__main__":
    create_play()