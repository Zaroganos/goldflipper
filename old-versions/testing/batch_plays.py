import json
import os
from datetime import datetime

# Template for the play data
play_template = {
    "symbol": "",
    "trade_type": "",  # CALL or PUT
    "entry_point": 0.0,
    "strike_price": 0.0,
    "expiration_date": "",
    "take_profit": {
        "stock_price": 0.0,
        "order_type": "market"
    },
    "stop_loss": {
        "stock_price": 0.0,
        "order_type": "market"
    },
    "contracts": 0,
    "order_class": "simple"
}

# Use the current directory to save the play files
plays_folder = "."
os.makedirs(plays_folder, exist_ok=True)

# Function to generate play files with cleaner filenames
def create_play_file(play_data):
    # Generate a computer-friendly filename with no symbols
    symbol = play_data['symbol'].replace("$", "").upper()  # Remove $ and ensure uppercase
    trade_type = play_data['trade_type'].upper()           # Ensure CALL/PUT is uppercase
    entry_point = play_data['entry_point']
    strike_price = play_data['strike_price']
    expiration_date = play_data['expiration_date'].replace("/", "_")  # Change date format to underscores
    
    # Final filename format: SYMBOL_TRADETYPE_STRIKEPRICE_EXPIRATIONDATE.json
    file_name = f"{symbol}_{trade_type}_{entry_point}_{strike_price}_{expiration_date}.json"
    file_path = os.path.join(plays_folder, file_name)
    
    try:
        with open(file_path, "w") as file:
            json.dump(play_data, file, indent=2)
        print(f"Play file '{file_name}' created successfully in the current directory.")
    except IOError as e:
        print(f"Error saving play file: {str(e)}")

# Data for 8 plays: 4 Calls and 4 Puts
option_plays = [
    # Calls
    {"symbol": "$SPY", "trade_type": "CALL", "entry_point": 562, "strike_price": 562, "expiration_date": "09/25/2024", "contracts": 1},
    {"symbol": "$SPY", "trade_type": "CALL", "entry_point": 575, "strike_price": 562, "expiration_date": "09/25/2024", "contracts": 1},
    {"symbol": "$SPY", "trade_type": "CALL", "entry_point": 562, "strike_price": 562, "expiration_date": "09/27/2024", "contracts": 1},
    {"symbol": "$SPY", "trade_type": "CALL", "entry_point": 575, "strike_price": 562, "expiration_date": "09/27/2024", "contracts": 1},
    
    # Puts
    {"symbol": "$SPY", "trade_type": "PUT", "entry_point": 562, "strike_price": 575, "expiration_date": "09/25/2024", "contracts": 1},
    {"symbol": "$SPY", "trade_type": "PUT", "entry_point": 575, "strike_price": 575, "expiration_date": "09/25/2024", "contracts": 1},
    {"symbol": "$SPY", "trade_type": "PUT", "entry_point": 562, "strike_price": 575, "expiration_date": "09/27/2024", "contracts": 1},
    {"symbol": "$SPY", "trade_type": "PUT", "entry_point": 575, "strike_price": 575, "expiration_date": "09/27/2024", "contracts": 1},
]

# Populate and create play files
for play in option_plays:
    play_data = play_template.copy()
    play_data["symbol"] = play["symbol"]
    play_data["trade_type"] = play["trade_type"]
    play_data["entry_point"] = play["entry_point"]
    play_data["strike_price"] = play["strike_price"]
    play_data["expiration_date"] = play["expiration_date"]
    play_data["contracts"] = play["contracts"]
    
    # Customize take_profit and stop_loss values based on strategy (if needed)
    play_data["take_profit"]["stock_price"] = play_data["strike_price"] + 10  # Example TP logic
    play_data["stop_loss"]["stock_price"] = play_data["strike_price"] - 10  # Example SL logic
    
    # Create play file
    create_play_file(play_data)
