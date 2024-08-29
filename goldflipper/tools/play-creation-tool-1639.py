import os
import json
from datetime import datetime

def create_play():
    """
    Interactive tool to create a play for options trading, following the minimal template.
    """

    play = {}

    # Gather required inputs from the user
    play['symbol'] = input("Enter the ticker symbol (e.g., BA): ")
    play['trade_type'] = input("Enter the trade type (CALL or PUT): ")
    play['entry_point'] = float(input("Enter the entry price: "))
    play['strike_price'] = float(input("Enter the strike price: "))
    play['expiration_date'] = input("Enter the expiration date (MM/DD/YYYY): ")

    play['take_profit'] = {
        'order_type': input("Enter take profit order type (market or limit): "),
        'value': float(input("Enter take profit value (percentage or price): "))
    }

    stop_loss_values = input("Enter stop loss values (separate multiple values with semicolon ';'): ").split(';')
    play['stop_loss'] = {
        'order_type': input("Enter stop loss order type (stop or stop_limit): "),
        'values': [float(value) for value in stop_loss_values]
    }

    play['contracts'] = int(input("Enter the number of contracts: "))
    play['order_class'] = input("Enter the order class (simple or OCO): ")

    # Determine the base directory of the goldflipper project
    goldflipper_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    plays_dir = os.path.join(goldflipper_dir, 'goldflipper', 'plays')
    
    # Ensure the plays directory exists
    os.makedirs(plays_dir, exist_ok=True)

    # Save to JSON
    filename = f"{play['symbol']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = os.path.join(plays_dir, filename)
    with open(filepath, 'w') as f:
        json.dump(play, f, indent=4)

    print(f"Play saved to {filepath}")

# Run the tool
create_play()
