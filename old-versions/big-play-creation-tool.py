import json
import os
from datetime import datetime

# Load the JSON play template
template_path = 'play-template.json'  # Path to the JSON play template

with open(template_path, 'r') as template_file:
    template = json.load(template_file)


# Function to create a new play file
def create_play_file(play_name, play_data):
    """
    Creates a new JSON play file based on the provided play name and data.
    
    Parameters:
    - play_name (str): The name of the play to be created.
    - play_data (dict): The data to be populated in the play file.
    
    Returns:
    - None
    """
    play_filename = f"{play_name.lower().replace(' ', '_')}.json"
    play_data["timestamp"] = datetime.now().isoformat()

    # Combine the template with the specific play data
    play_content = template.copy()
    play_content.update(play_data)

    # Correct path to the plays directory
    output_dir = r"C:\Users\Iliya\Documents\GitHub\goldflipper\goldflipper\plays"
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, play_filename)
    with open(output_path, 'w') as play_file:
        json.dump(play_content, play_file, indent=4)

    print(f"Play file created: {output_path}")


# Function to display the play data
def display_play(play_data):
    """
    Display the play data in a user-friendly format.

    Parameters:
    - play_data (dict): The play data to be displayed.

    Returns:
    - None
    """
    for key, value in play_data.items():
        if isinstance(value, dict):
            print(f"{key}:")
            for sub_key, sub_value in value.items():
                print(f"  {sub_key}: {sub_value}")
        else:
            print(f"{key}: {value}")
    print()

# Function to validate the play data against the template
def validate_play(play_data):
    """
    Validates the play data against the template structure.

    Parameters:
    - play_data (dict): The play data to be validated.

    Returns:
    - bool: True if valid, False otherwise.
    """
    for key in template.keys():
        if key not in play_data:
            print(f"Warning: Missing key '{key}' in play data.")
            return False
    return True

# Function to load a play from an existing JSON file
def load_play(play_filename):
    """
    Load a play from an existing JSON file.

    Parameters:
    - play_filename (str): The filename of the play to be loaded.

    Returns:
    - dict: The loaded play data.
    """
    with open(play_filename, 'r') as play_file:
        play_data = json.load(play_file)
    return play_data

# Function to update an existing play
def update_play(play_filename, updates):
    """
    Update an existing play with new data.

    Parameters:
    - play_filename (str): The filename of the play to be updated.
    - updates (dict): The data to be updated.

    Returns:
    - None
    """
    play_data = load_play(play_filename)
    play_data.update(updates)
    with open(play_filename, 'w') as play_file:
        json.dump(play_data, play_file, indent=4)
    print(f"Play file updated: {play_filename}")

# Function to delete a play file
def delete_play(play_filename):
    """
    Delete a play file.

    Parameters:
    - play_filename (str): The filename of the play to be deleted.

    Returns:
    - None
    """
    os.remove(play_filename)
    print(f"Play file deleted: {play_filename}")


# Function to input play data with embedded comments and defaults
def input_play_data():
    """
    Gathers input for creating a new play, matching the template with comments,
    and providing defaults and guidance.
    
    Returns:
    - dict: The input play data.
    """
    play_data = {}
    
    play_data["play_id"] = input("Enter play ID (e.g., META_CALL_2024): ")
    play_data["status"] = input("Enter play status (default: 'pending'): ") or "pending"
    play_data["strategy"] = input("Enter strategy (default: 'Options Swing'): ") or "Options Swing"
    play_data["ticker"] = input("Enter the ticker symbol (e.g., META): ")
    play_data["trade_type"] = input("Enter the trade type (CALL or PUT): ").upper()
    play_data["market_context"] = input("Enter market context (e.g., 'Trading Range 4H: 461.20 - 481.1'): ")
    play_data["entry_point"] = float(input("Enter the entry point (e.g., 463.15): "))

    print("\n--- Order Details ---")
    order_details = {}
    order_details["symbol"] = play_data["ticker"]
    order_details["qty"] = input("Enter the number of contracts (default: 10): ") or "10"
    order_details["side"] = "buy" if play_data["trade_type"] == "CALL" else "sell"
    order_details["type"] = input("Enter the order type (limit, market, stop, stop_limit) (default: 'limit'): ") or "limit"
    order_details["time_in_force"] = input("Enter time in force (day, gtc) (default: 'day'): ") or "day"
    
    if order_details["type"] in ["limit", "stop_limit"]:
        order_details["limit_price"] = input("Enter the limit price (e.g., 463.15): ")
    if order_details["type"] in ["stop", "stop_limit"]:
        order_details["stop_price"] = input("Enter the stop price (e.g., 460.0): ")
    if order_details["type"] == "trailing_stop":
        order_details["trail_price"] = input("Enter the trailing stop price (optional): ")
        order_details["trail_percent"] = input("Enter the trailing stop percent (optional): ")

    print("\n--- Take Profit Levels ---")
    take_profit = []
    for i in range(1, 3):  # Example allows up to 2 TPs
        tp = {}
        tp["tp_id"] = f"TP{i}"
        tp["order_type"] = input(f"Enter TP{i} order type (market, limit) (default: 'market'): ") or "market"
        tp["price"] = float(input(f"Enter TP{i} price (e.g., 473.9): "))
        tp["contracts"] = int(input(f"Enter TP{i} contracts (default: {order_details['qty']}): ") or order_details["qty"])
        take_profit.append(tp)
    play_data["take_profit"] = take_profit
    
    print("\n--- Stop Loss ---")
    stop_loss = {}
    stop_loss["order_type"] = input("Enter the stop loss order type (stop, stop_limit) (default: 'stop'): ") or "stop"
    stop_loss["price"] = input("Enter the stop loss price (or percentage, e.g., -35%): ")
    stop_loss["contracts"] = order_details["qty"]  # Default to all contracts
    play_data["stop_loss"] = stop_loss
    
    play_data["order_details"] = order_details
    return play_data

# Main menu for the Play Creation Tool
def main_menu():
    """
    Main menu for interacting with the Play Creation Tool.

    Returns:
    - None
    """
    while True:
        print("Play Creation Tool Menu")
        print("1. Create a new play")
        print("2. Display a play")
        print("3. Validate a play")
        print("4. Update a play")
        print("5. Delete a play")
        print("6. Exit")
        choice = input("Enter your choice: ")

        if choice == '1':
            play_name = input("Enter the play name: ")
            play_data = input_play_data()
            create_play_file(play_name, play_data)

        elif choice == '2':
            play_filename = input("Enter the filename of the play to display: ")
            play_data = load_play(play_filename)
            display_play(play_data)

        elif choice == '3':
            play_filename = input("Enter the filename of the play to validate: ")
            play_data = load_play(play_filename)
            if validate_play(play_data):
                print("Play is valid.")
            else:
                print("Play is invalid.")

        elif choice == '4':
            play_filename = input("Enter the filename of the play to update: ")
            updates = {
                "status": input("Enter new status: "),
            }
            update_play(play_filename, updates)

        elif choice == '5':
            play_filename = input("Enter the filename of the play to delete: ")
            delete_play(play_filename)

        elif choice == '6':
            print("Exiting Play Creation Tool.")
            break

        else:
            print("Invalid choice. Please try again.")

# Example usage
if __name__ == "__main__":
    main_menu()
