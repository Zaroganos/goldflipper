import os
import json
import re
from datetime import datetime
import platform
import subprocess
import yaml
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from goldflipper.utils.display import TerminalDisplay
from colorama import Fore, Style

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
    TerminalDisplay.info("\nSelect price condition type(s):", show_timestamp=False)
    print(f"{Fore.CYAN}1. Stock price (absolute value)")
    print("2. Option premium %")
    print(f"3. Stock price % movement{Style.RESET_ALL}")
    print("Enter your choices (separated by space, comma, or dash). Examples: '1 2 3' or '1,2' or '1-3'")
    
    return get_input(
        "Choice (1-5): ",
        int,
        validation=lambda x: x in [1, 2, 3, 4, 5],
        error_message="Please enter a number between 1 and 5."
    )

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

def create_play():
    """
    Interactive tool to create a play for options trading, following the minimal template.
    """
    TerminalDisplay.header("Options Play Creation Tool", show_timestamp=False)
    
    while True:
        play = {}

        TerminalDisplay.info("Enter play details:", show_timestamp=False)
        
        play['symbol'] = get_input(
            f"{Fore.CYAN}Enter the ticker symbol (e.g., SPY): {Style.RESET_ALL}",
            str,
            validation=lambda x: len(x) > 0,
            error_message="Ticker symbol cannot be empty."
        ).upper()

        play['trade_type'] = get_input(
            f"{Fore.CYAN}Enter the trade type (CALL or PUT): {Style.RESET_ALL}",
            str,
            validation=lambda x: validate_choice(x, ["CALL", "PUT"]),
            error_message="Invalid trade type. Please enter 'CALL' or 'PUT'."
        ).upper()

        # Entry point setup
        TerminalDisplay.info("\nSetting Entry Point Parameters:", show_timestamp=False)
        play['entry_point'] = {}
        play['entry_point']['stock_price'] = get_input(
            f"{Fore.CYAN}Enter the entry stock price: {Style.RESET_ALL}",
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
            TerminalDisplay.success(f"Generated option contract symbol: {play['option_contract_symbol']}", show_timestamp=False)
        except ValueError as ve:
            TerminalDisplay.error(f"Error generating option contract symbol: {ve}", show_timestamp=False)
            return

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
        TerminalDisplay.header("Take Profit Configuration", show_timestamp=False)
        tp_price_type = get_price_condition_type()
        play['take_profit'] = {
            'stock_price': None,
            'stock_price_pct': None,
            'premium_pct': None,
            'order_type': 'market'
        }

        if tp_price_type in [1, 4]:  # Absolute stock price
            tp_stock_price = get_input(
                "Enter take profit stock price: ",
                float,
                validation=lambda x: x > 0,
                error_message="Please enter a valid positive number for the take profit stock price."
            )
            play['take_profit']['stock_price'] = tp_stock_price

        elif tp_price_type == 3:  # Stock price % movement only
            tp_stock_price_pct = get_input(
                "Enter take profit stock price percentage movement: ",
                float,
                validation=lambda x: x > 0,
                error_message="Please enter a valid positive percentage"
            )
            play['take_profit']['stock_price_pct'] = tp_stock_price_pct

        if tp_price_type in [2, 4, 5]:  # Any condition involving premium %
            tp_premium_pct = get_premium_percentage()
            play['take_profit']['premium_pct'] = tp_premium_pct

        if tp_price_type == 5:  # Stock price % + premium %
            tp_stock_price_pct = get_input(
                "Enter take profit stock price percentage movement: ",
                float,
                validation=lambda x: x > 0,
                error_message="Please enter a valid positive percentage"
            )
            play['take_profit']['stock_price_pct'] = tp_stock_price_pct

        # Take profit order type
        play['take_profit']['order_type'] = get_order_type_choice(transaction_type="Take Profit")

        # Stop loss section
        TerminalDisplay.header("Stop Loss Configuration", show_timestamp=False)
        sl_price_type = get_price_condition_type()
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
            if sl_price_type in [1, 4]:  # Absolute stock price
                sl_stock_price = get_input(
                    "Enter stop loss stock price: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive number for the stop loss stock price."
                )
                play['stop_loss']['stock_price'] = sl_stock_price

            elif sl_price_type == 3:  # Stock price % movement only
                sl_stock_price_pct = get_input(
                    "Enter stop loss stock price percentage movement: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive percentage"
                )
                play['stop_loss']['stock_price_pct'] = sl_stock_price_pct

            if sl_price_type in [2, 4, 5]:  # Any condition involving premium %
                sl_premium_pct = get_premium_percentage()
                play['stop_loss']['premium_pct'] = sl_premium_pct

            if sl_price_type == 5:  # Stock price % + premium %
                sl_stock_price_pct = get_input(
                    "Enter stop loss stock price percentage movement: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive percentage"
                )
                play['stop_loss']['stock_price_pct'] = sl_stock_price_pct

        else:  # CONTINGENCY type needs two sets of conditions
            if sl_price_type in [1, 4]:  # Absolute stock price
                TerminalDisplay.info("\nEnter main stop loss conditions:", show_timestamp=False)
                main_stock_price = get_input(
                    "Enter main stop loss stock price: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive number for the main stop loss stock price."
                )
                
                while True:
                    TerminalDisplay.info("\nEnter backup/safety stop loss conditions (must be worse than main price):", show_timestamp=False)
                    backup_stock_price = get_input(
                        f"Enter backup stop loss stock price ({'lower' if play['trade_type'] == 'CALL' else 'higher'} than {main_stock_price}): ",
                        float,
                        validation=lambda x: x > 0,
                        error_message="Please enter a valid positive number for the backup stop loss stock price."
                    )
                    
                    if validate_contingency_prices(main_stock_price, backup_stock_price, True, play['trade_type']):
                        break
                    TerminalDisplay.error(f"Error: Backup price must be {'lower' if play['trade_type'] == 'CALL' else 'higher'} than the main price ({main_stock_price}) for a {play['trade_type']}", show_timestamp=False)
                
                play['stop_loss']['stock_price'] = main_stock_price
                play['stop_loss']['contingency_stock_price'] = backup_stock_price

            elif sl_price_type == 3:  # Stock price % movement only
                TerminalDisplay.info("\nEnter main stop loss conditions:", show_timestamp=False)
                main_stock_price_pct = get_input(
                    "Enter main stop loss stock price percentage movement: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive percentage"
                )
                
                while True:
                    TerminalDisplay.info("\nEnter backup/safety stop loss conditions (must represent a bigger movement):", show_timestamp=False)
                    backup_stock_price_pct = get_input(
                        "Enter backup stop loss stock price percentage movement (must be higher than main %): ",
                        float,
                        validation=lambda x: x > main_stock_price_pct,
                        error_message=f"Please enter a percentage higher than {main_stock_price_pct}%"
                    )
                    
                    if backup_stock_price_pct > main_stock_price_pct:
                        break
                    TerminalDisplay.error(f"Error: Backup percentage ({backup_stock_price_pct}%) must be higher than main percentage ({main_stock_price_pct}%)", show_timestamp=False)
                
                play['stop_loss']['stock_price_pct'] = main_stock_price_pct
                play['stop_loss']['contingency_stock_price_pct'] = backup_stock_price_pct

            if sl_price_type in [2, 4, 5]:  # Any condition involving premium %
                TerminalDisplay.info("\nEnter main stop loss conditions:", show_timestamp=False) if sl_price_type == 2 else None
                main_premium = get_premium_percentage()
                
                while True:
                    TerminalDisplay.info("\nEnter backup/safety stop loss conditions (must represent a bigger loss):", show_timestamp=False)
                    TerminalDisplay.info(f"Current main stop loss is at {main_premium}% loss from entry", show_timestamp=False)
                    TerminalDisplay.info(f"Backup must be higher than {main_premium}% (representing a bigger loss)", show_timestamp=False)
                    backup_premium = get_premium_percentage()
                    
                    if validate_contingency_prices(main_premium, backup_premium, False, play['trade_type']):
                        break
                    TerminalDisplay.error(f"Error: Backup loss percentage ({backup_premium}%) must be higher than main loss percentage ({main_premium}%) to represent a bigger loss", show_timestamp=False)
                
                play['stop_loss']['premium_pct'] = main_premium
                play['stop_loss']['contingency_premium_pct'] = backup_premium

            if sl_price_type == 5:  # Stock price % + premium %
                TerminalDisplay.info("\nEnter main stop loss conditions:", show_timestamp=False)
                main_stock_price_pct = get_input(
                    "Enter main stop loss stock price percentage movement: ",
                    float,
                    validation=lambda x: x > 0,
                    error_message="Please enter a valid positive percentage"
                )
                
                while True:
                    TerminalDisplay.info("\nEnter backup/safety stop loss conditions (must represent a bigger movement):", show_timestamp=False)
                    backup_stock_price_pct = get_input(
                        "Enter backup stop loss stock price percentage movement (must be higher than main %): ",
                        float,
                        validation=lambda x: x > main_stock_price_pct,
                        error_message=f"Please enter a percentage higher than {main_stock_price_pct}%"
                    )
                    
                    if backup_stock_price_pct > main_stock_price_pct:
                        break
                    TerminalDisplay.error(f"Error: Backup percentage ({backup_stock_price_pct}%) must be higher than main percentage ({main_stock_price_pct}%)", show_timestamp=False)
                
                play['stop_loss']['stock_price_pct'] = main_stock_price_pct
                play['stop_loss']['contingency_stock_price_pct'] = backup_stock_price_pct

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

        TerminalDisplay.success(f"Play saved successfully to {filepath}", show_timestamp=False)

        # Open the file in text editor
        try:
            if platform.system() == "Windows":
                subprocess.run(["notepad.exe", filepath])
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", "-t", filepath])
            else:  # Linux
                subprocess.run(["xdg-open", filepath])
            TerminalDisplay.info("Opening play file in text editor...", show_timestamp=False)
        except Exception as e:
            TerminalDisplay.warning(f"Could not open file automatically: {e}", show_timestamp=False)

        

        # Ask the user if they want to create another play
        another_play = get_input(
            f"{Fore.CYAN}Do you want to create another play? (Y/N): {Style.RESET_ALL}",
            str,
            validation=lambda x: x.upper() in ["Y", "N"],
            error_message="Please enter 'Y' or 'N'."
        ).upper()

        if another_play == "Y":
            os.system('cls' if platform.system() == "Windows" else 'clear')  # Clear the screen
            return create_play()
        else:
            TerminalDisplay.info("Exiting the play creation tool.", show_timestamp=False)
            return

if __name__ == "__main__":
    create_play()