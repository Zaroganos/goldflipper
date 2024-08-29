import os
import json
from datetime import datetime

def get_input(prompt, input_type=str, validation=None, error_message="Invalid input. Please try again."):
    """
    Helper function to get validated input from the user.

    Parameters:
    - prompt (str): The message to show the user.
    - input_type (type): The type to convert the input into (e.g., int, float, str).
    - validation (function): A function that takes the input and returns True if valid, False otherwise.
    - error_message (str): The message to show if validation fails.

    Returns:
    - The validated input converted to input_type.
    """
    while True:
        try:
            user_input = input_type(input(prompt).strip())
            if validation and not validation(user_input):
                print(error_message)
            else:
                return user_input
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

def create_play():
    """
    Interactive tool to create a play for options trading, following the minimal template.
    """

    play = {}

    play['symbol'] = get_input("Enter the ticker symbol (e.g., BA): ", str, validation=lambda x: len(x) > 0, error_message="Ticker symbol cannot be empty.")

    play['trade_type'] = get_input(
        "Enter the trade type (CALL or PUT): ",
        str,
        validation=lambda x: validate_choice(x, ["CALL", "PUT"]),
        error_message="Invalid trade type. Please enter 'CALL' or 'PUT'."
    )

    play['entry_point'] = get_input("Enter the entry price: ", float, error_message="Please enter a valid number for the entry price.")

    play['strike_price'] = get_input("Enter the strike price: ", float, error_message="Please enter a valid number for the strike price.")

    play['expiration_date'] = get_input(
        "Enter the expiration date (MM/DD/YYYY): ",
        str,
        validation=lambda x: datetime.strptime(x, "%m/%d/%Y"),
        error_message="Please enter a valid date in MM/DD/YYYY format."
    )

    play['take_profit'] = {
        'order_type': get_input(
            "Enter take profit order type (market or limit): ",
            str,
            validation=lambda x: validate_choice(x, ["MARKET", "LIMIT"]),
            error_message="Invalid order type. Please enter 'market' or 'limit'."
        ),
        'value': get_input("Enter take profit value (percentage or price): ", float, error_message="Please enter a valid number for the take profit value.")
    }

    stop_loss_values = get_input(
        "Enter stop loss values (separate multiple values with semicolon ';'): ",
        str,
        validation=lambda x: all(v.strip().isdigit() for v in x.split(';')),
        error_message="Please enter valid numbers separated by semicolons for stop loss values."
    ).split(';')
    
    play['stop_loss'] = {
        'order_type': get_input(
            "Enter stop loss order type (stop or stop_limit): ",
            str,
            validation=lambda x: validate_choice(x, ["STOP", "STOP_LIMIT"]),
            error_message="Invalid order type. Please enter 'stop' or 'stop_limit'."
        ),
        'values': [float(value) for value in stop_loss_values]
    }

    play['contracts'] = get_input("Enter the number of contracts: ", int, validation=lambda x: x > 0, error_message="Please enter a positive integer for the number of contracts.")

    play['order_class'] = get_input(
        "Enter the order class (simple or OCO): ",
        str,
        validation=lambda x: validate_choice(x, ["SIMPLE", "OCO"]),
        error_message="Invalid order class. Please enter 'simple' or 'OCO'."
    )

    plays_dir = os.path.join(os.path.dirname(__file__), '..', 'plays')
    os.makedirs(plays_dir, exist_ok=True)

    filename = f"{play['symbol']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = os.path.join(plays_dir, filename)
    with open(filepath, 'w') as f:
        json.dump(play, f, indent=4)

    print(f"Play saved to {filepath}")

if __name__ == "__main__":
    create_play()
