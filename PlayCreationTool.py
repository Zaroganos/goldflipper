import os
import json
from datetime import datetime

# Define the path to the "plays" folder
plays_folder = os.path.join(os.path.expanduser("~"), "plays")
os.makedirs(plays_folder, exist_ok=True)

# Define the play template based on the latest JSON structure
play_template = {
    "play_id": "",
    "timestamp": "",
    "status": "",
    "strategy": "",
    "underlying_asset": {
        "symbol": "",
        "name": "",
        "type": "",
        "exchange": "",
        "price": {
            "current": 0.0,
            "range": {
                "low": 0.0,
                "high": 0.0
            }
        },
        "currency": "",
        "comments": {
            "symbol": "",
            "name": "",
            "type": "",
            "exchange": "",
            "price": "",
            "currency": ""
        }
    },
    "option_contract": {
        "symbol": "",
        "type": "",
        "strike_price": 0.0,
        "expiration_date": "",
        "premium": {
            "current": 0.0,
            "range": {
                "low": 0.0,
                "high": 0.0
            }
        },
        "quantity": 0,
        "greeks": {
            "delta": { "value": 0.0, "range": { "low": 0.0, "high": 0.0 } },
            "gamma": { "value": 0.0, "range": { "low": 0.0, "high": 0.0 } },
            "theta": { "value": 0.0, "range": { "low": 0.0, "high": 0.0 } },
            "vega": { "value": 0.0, "range": { "low": 0.0, "high": 0.0 } },
            "rho": { "value": 0.0, "range": { "low": 0.0, "high": 0.0 } }
        },
        "implied_volatility": { "value": 0.0, "range": { "low": 0.0, "high": 0.0 } },
        "historical_volatility": { "value": 0.0, "range": { "low": 0.0, "high": 0.0 } },
        "days_to_expiration": 0,
        "risk_free_rate": 0.0,
        "bid_ask_spread": 0.0,
        "comments": {
            "symbol": "",
            "type": "",
            "strike_price": "",
            "expiration_date": "",
            "premium": "",
            "quantity": "",
            "greeks": "",
            "implied_volatility": "",
            "historical_volatility": "",
            "days_to_expiration": "",
            "risk_free_rate": "",
            "bid_ask_spread": ""
        }
    },
    "entry": {
        "price": {
            "stock": 0.0,
            "option": 0.0
        },
        "timestamp": "",
        "order_type": "",
        "position_size": 0,
        "chart_timeframes": [],
        "comments": {
            "price": "",
            "timestamp": "",
            "order_type": "",
            "position_size": "",
            "chart_timeframes": ""
        }
    },
    "exit": {
        "take_profit": {
            "price": {
                "stock": 0.0,
                "option": 0.0
            },
            "timestamp": "",
            "order_type": ""
        },
        "stop_loss": {
            "price": {
                "stock": 0.0,
                "option": 0.0
            },
            "timestamp": "",
            "order_type": ""
        },
        "comments": {
            "take_profit": "",
            "stop_loss": "",
            "timestamp": "",
            "order_type": ""
        }
    },
    "risk_management": {
        "max_profit_potential": 0.0,
        "max_loss_potential": 0.0,
        "risk_reward_ratio": 0.0,
        "probability_of_profit": 0.0,
        "break_even_points": [],
        "margin_requirement": 0.0,
        "position_size_percentage": 0.0,
        "comments": {
            "max_profit_potential": "",
            "max_loss_potential": "",
            "risk_reward_ratio": "",
            "probability_of_profit": "",
            "break_even_points": "",
            "margin_requirement": "",
            "position_size_percentage": ""
        }
    },
    # Additional sections would be similarly defined here...
}

def get_user_input(field, field_type, default_value=None):
    while True:
        user_input = input(f"Enter {field} (press Enter to skip): ")
        if user_input == "":
            return default_value
        if field_type == "number":
            try:
                return float(user_input)
            except ValueError:
                print("Invalid input. Please enter a valid number.")
        elif field_type == "integer":
            try:
                return int(user_input)
            except ValueError:
                print("Invalid input. Please enter a valid integer.")
        elif field_type == "list":
            return [item.strip() for item in user_input.split(",")]
        else:
            return user_input

def input_underlying_asset():
    """Function to input data for the underlying asset section."""
    underlying_asset = play_template["underlying_asset"].copy()
    underlying_asset["symbol"] = get_user_input("underlying asset symbol", "string")
    underlying_asset["name"] = get_user_input("underlying asset name", "string")
    underlying_asset["type"] = get_user_input("underlying asset type", "string")
    underlying_asset["exchange"] = get_user_input("underlying asset exchange", "string")
    underlying_asset["price"]["current"] = get_user_input("current price", "number")
    underlying_asset["price"]["range"]["low"] = get_user_input("price range low", "number")
    underlying_asset["price"]["range"]["high"] = get_user_input("price range high", "number")
    underlying_asset["currency"] = get_user_input("currency", "string", "USD")

    # Input comments for the underlying asset
    underlying_asset["comments"]["symbol"] = get_user_input("comments on symbol", "string")
    underlying_asset["comments"]["name"] = get_user_input("comments on name", "string")
    underlying_asset["comments"]["type"] = get_user_input("comments on type", "string")
    underlying_asset["comments"]["exchange"] = get_user_input("comments on exchange", "string")
    underlying_asset["comments"]["price"] = get_user_input("comments on price", "string")
    underlying_asset["comments"]["currency"] = get_user_input("comments on currency", "string")

    return underlying_asset

def input_option_contract():
    """Function to input data for the option contract section."""
    option_contract = play_template["option_contract"].copy()
    option_contract["symbol"] = get_user_input("option contract symbol", "string")
    option_contract["type"] = get_user_input("option contract type (call/put)", "string")
    option_contract["strike_price"] = get_user_input("strike price", "number")
    option_contract["expiration_date"] = get_user_input("expiration date (YYYY-MM-DD)", "string")
    option_contract["premium"]["current"] = get_user_input("current premium", "number")
    option_contract["premium"]["range"]["low"] = get_user_input("premium range low", "number")
    option_contract["premium"]["range"]["high"] = get_user_input("premium range high", "number")
    option_contract["quantity"] = get_user_input("quantity", "integer")
    
    # Greeks
    option_contract["greeks"]["delta"]["value"] = get_user_input("delta value", "number")
    option_contract["greeks"]["gamma"]["value"] = get_user_input("gamma value", "number")
    option_contract["greeks"]["theta"]["value"] = get_user_input("theta value", "number")
    option_contract["greeks"]["vega"]["value"] = get_user_input("vega value", "number")
    option_contract["greeks"]["rho"]["value"] = get_user_input("rho value", "number")
    
    option_contract["implied_volatility"]["value"] = get_user_input("implied volatility value", "number")
    option_contract["historical_volatility"]["value"] = get_user_input("historical volatility value", "number")
    option_contract["days_to_expiration"] = get_user_input("days to expiration", "integer")
    option_contract["risk_free_rate"] = get_user_input("risk-free rate", "number")
    option_contract["bid_ask_spread"] = get_user_input("bid-ask spread", "number")
    
    # Input comments for the option contract
    option_contract["comments"]["symbol"] = get_user_input("comments on symbol", "string")
    option_contract["comments"]["type"] = get_user_input("comments on type", "string")
    option_contract["comments"]["strike_price"] = get_user_input("comments on strike price", "string")
    option_contract["comments"]["expiration_date"] = get_user_input("comments on expiration date", "string")
    option_contract["comments"]["premium"] = get_user_input("comments on premium", "string")
    option_contract["comments"]["quantity"] = get_user_input("comments on quantity", "string")
    option_contract["comments"]["greeks"] = get_user_input("comments on greeks", "string")
    option_contract["comments"]["implied_volatility"] = get_user_input("comments on implied volatility", "string")
    option_contract["comments"]["historical_volatility"] = get_user_input("comments on historical volatility", "string")
    option_contract["comments"]["days_to_expiration"] = get_user_input("comments on days to expiration", "string")
    option_contract["comments"]["risk_free_rate"] = get_user_input("comments on risk-free rate", "string")
    option_contract["comments"]["bid_ask_spread"] = get_user_input("comments on bid-ask spread", "string")
    
    return option_contract

def input_entry():
    """Function to input data for the entry section."""
    entry = play_template["entry"].copy()
    entry["price"]["stock"] = get_user_input("entry stock price", "number")
    entry["price"]["option"] = get_user_input("entry option price", "number")
    entry["timestamp"] = get_user_input("entry timestamp (YYYY-MM-DD HH:MM:SS)", "string")
    entry["order_type"] = get_user_input("entry order type", "string")
    entry["position_size"] = get_user_input("entry position size", "integer")
    entry["chart_timeframes"] = get_user_input("entry chart timeframes (comma separated)", "list")
    
    # Input comments for the entry section
    entry["comments"]["price"] = get_user_input("comments on entry price", "string")
    entry["comments"]["timestamp"] = get_user_input("comments on entry timestamp", "string")
    entry["comments"]["order_type"] = get_user_input("comments on entry order type", "string")
    entry["comments"]["position_size"] = get_user_input("comments on entry position size", "string")
    entry["comments"]["chart_timeframes"] = get_user_input("comments on entry chart timeframes", "string")
    
    return entry

def input_exit():
    """Function to input data for the exit section."""
    exit = play_template["exit"].copy()
    
    # Take profit
    exit["take_profit"]["price"]["stock"] = get_user_input("take profit stock price", "number")
    exit["take_profit"]["price"]["option"] = get_user_input("take profit option price", "number")
    exit["take_profit"]["timestamp"] = get_user_input("take profit timestamp (YYYY-MM-DD HH:MM:SS)", "string")
    exit["take_profit"]["order_type"] = get_user_input("take profit order type", "string")
    
    # Stop loss
    exit["stop_loss"]["price"]["stock"] = get_user_input("stop loss stock price", "number")
    exit["stop_loss"]["price"]["option"] = get_user_input("stop loss option price", "number")
    exit["stop_loss"]["timestamp"] = get_user_input("stop loss timestamp (YYYY-MM-DD HH:MM:SS)", "string")
    exit["stop_loss"]["order_type"] = get_user_input("stop loss order type", "string")
    
    # Input comments for the exit section
    exit["comments"]["take_profit"] = get_user_input("comments on take profit", "string")
    exit["comments"]["stop_loss"] = get_user_input("comments on stop loss", "string")
    exit["comments"]["timestamp"] = get_user_input("comments on exit timestamp", "string")
    exit["comments"]["order_type"] = get_user_input("comments on exit order type", "string")
    
    return exit

def input_risk_management():
    """Function to input data for the risk management section."""
    risk_management = play_template["risk_management"].copy()
    risk_management["max_profit_potential"] = get_user_input("max profit potential", "number")
    risk_management["max_loss_potential"] = get_user_input("max loss potential", "number")
    risk_management["risk_reward_ratio"] = get_user_input("risk-reward ratio", "number")
    risk_management["probability_of_profit"] = get_user_input("probability of profit", "number")
    risk_management["break_even_points"] = get_user_input("break-even points (comma separated)", "list")
    risk_management["margin_requirement"] = get_user_input("margin requirement", "number")
    risk_management["position_size_percentage"] = get_user_input("position size percentage", "number")
    
    # Input comments for the risk management section
    risk_management["comments"]["max_profit_potential"] = get_user_input("comments on max profit potential", "string")
    risk_management["comments"]["max_loss_potential"] = get_user_input("comments on max loss potential", "string")
    risk_management["comments"]["risk_reward_ratio"] = get_user_input("comments on risk-reward ratio", "string")
    risk_management["comments"]["probability_of_profit"] = get_user_input("comments on probability of profit", "string")
    risk_management["comments"]["break_even_points"] = get_user_input("comments on break-even points", "string")
    risk_management["comments"]["margin_requirement"] = get_user_input("comments on margin requirement", "string")
    risk_management["comments"]["position_size_percentage"] = get_user_input("comments on position size percentage", "string")
    
    return risk_management

def create_play_file():
    play_data = play_template.copy()

    # Get user input for main fields
    play_data["play_id"] = get_user_input("play ID", "string")
    play_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    play_data["status"] = get_user_input("status", "string", "pending")
    play_data["strategy"] = get_user_input("strategy", "string")

    # Gather data for each section
    play_data["underlying_asset"] = input_underlying_asset()
    play_data["option_contract"] = input_option_contract()
    play_data["entry"] = input_entry()
    play_data["exit"] = input_exit()
    play_data["risk_management"] = input_risk_management()
    
    # Call other functions for additional sections as needed...

    # Save the play data as a JSON file
    file_name = f"{play_data['play_id']}_{play_data['timestamp'].replace(':', '-').replace(' ', '_')}.json"
    file_path = os.path.join(plays_folder, file_name)

    try:
        with open(file_path, "w") as file:
            json.dump(play_data, file, indent=2)
        print(f"Play file '{file_name}' created successfully in the 'plays' folder.")
    except IOError as e:
        print(f"Error occurred while saving the play file: {str(e)}")

if __name__ == "__main__":
    try:
        create_play_file()
    except KeyboardInterrupt:
        print("\nScript interrupted by the user.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
