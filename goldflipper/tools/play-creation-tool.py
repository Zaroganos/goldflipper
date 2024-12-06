import os
import json
import re
from datetime import datetime
import platform
import subprocess

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

def get_condition_type_choice():
    """Get user's choice for condition type."""
    return get_input(
        "Please choose condition type:\n"
        "1. Stock price only\n"
        "2. Option premium % only\n"
        "3. Both stock price and option premium %\n"
        "Choice (1/2/3): ",
        int,
        validation=lambda x: x in [1, 2, 3],
        error_message="Please enter 1 for stock price, 2 for option premium %, or 3 for both."
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

        play['entry_point'] = get_input(
            "Enter the entry price (stock price): ",
            float,
            error_message="Please enter a valid number for the entry price."
        )

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

        # Entry order type
        play['entry_order_type'] = get_order_type_choice(transaction_type="Entry")
        
        # Take profit section
        print("\nSetting Take Profit conditions...")
        tp_type = get_condition_type_choice()
        play['take_profit'] = {'stock_price': None, 'premium_pct': None, 'order_type': 'market'}
        
        if tp_type in [1, 3]:  # Stock price or both
            tp_stock_price = get_input(
                "Enter take profit stock price: ",
                float,
                validation=lambda x: x > 0,
                error_message="Please enter a valid positive number for the take profit stock price."
            )
            play['take_profit']['stock_price'] = tp_stock_price

        if tp_type in [2, 3]:  # Premium % or both
            tp_premium_pct = get_premium_percentage()
            play['take_profit']['premium_pct'] = tp_premium_pct
        
        # Take profit order type
        play['take_profit']['order_type'] = get_order_type_choice(transaction_type="Take Profit")

        # Stop loss section
        print("\nSetting Stop Loss conditions...")
        sl_type = get_condition_type_choice()
        play['stop_loss'] = {'stock_price': None, 'premium_pct': None, 'order_type': 'market'}
        
        if sl_type in [1, 3]:  # Stock price or both
            sl_stock_price = get_input(
                "Enter stop loss stock price: ",
                float,
                validation=lambda x: x > 0,
                error_message="Please enter a valid positive number for the stop loss stock price."
            )
            play['stop_loss']['stock_price'] = sl_stock_price

        if sl_type in [2, 3]:  # Premium % or both
            sl_premium_pct = get_premium_percentage()
            play['stop_loss']['premium_pct'] = sl_premium_pct
        
        # Stop loss order type
        play['stop_loss']['order_type'] = get_order_type_choice(is_stop_loss=True, transaction_type="Stop Loss")

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

        # Update the plays directory path
        if play['play_class'] == 'OTO':
            plays_dir = os.path.join(os.path.dirname(__file__), '..', 'plays', 'temp')
        else:
            plays_dir = os.path.join(os.path.dirname(__file__), '..', 'plays', 'new')
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