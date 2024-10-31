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

def create_play():
    """
    Interactive tool to create a play for options trading, following the minimal template.
    """

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
        "Enter the expiration date (MM/DD/YYYY): ",
        str,
        validation=lambda x: datetime.strptime(x, "%m/%d/%Y"),
        error_message="Please enter a valid date in MM/DD/YYYY format."
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
    take_profit_stock_price = get_input(
        "Enter take profit stock price: ",
        float,
        validation=lambda x: x > 0,
        error_message="Please enter a valid positive number for the take profit stock price."
    )

    play['take_profit'] = {
        'stock_price': take_profit_stock_price,
        'order_type': 'market'
    }

    # Stop loss section
    stop_loss_stock_price = get_input(
        "Enter stop loss stock price: ",
        float,
        validation=lambda x: x > 0,
        error_message="Please enter a valid positive number for the stop loss stock price."
    )

    play['stop_loss'] = {
        'stock_price': stop_loss_stock_price,
        'order_type': 'market'
    }

    play['contracts'] = get_input(
        "Enter the number of contracts: ",
        int,
        validation=lambda x: x > 0,
        error_message="Please enter a positive integer for the number of contracts."
    )

    play['order_class'] = 'simple'  # Simplified to always use 'simple' order class

    # Update the plays directory path
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

if __name__ == "__main__":
    create_play()