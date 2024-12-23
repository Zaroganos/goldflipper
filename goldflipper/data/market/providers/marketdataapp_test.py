import sys
import os
from datetime import datetime

# Add the project root to the PYTHONPATH
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from goldflipper.data.market.providers.marketdataapp_provider import MarketDataAppProvider

def main(config_path: str):
    # Initialize the provider
    provider = MarketDataAppProvider(config_path)
    
    # Prompt the user for input
    symbol = input("Enter the stock symbol (e.g., AAPL): ").strip().upper()
    expiration_date = input("Enter the expiration date (YYYY-MM-DD) or leave blank for nearest: ").strip()
    
    try:
        # Fetch the option chain
        option_chain = provider.get_option_chain(symbol, expiration_date if expiration_date else None)
        
        # Display the option chain in a human-readable format
        print("\nOption Chain for:", symbol)
        print("Calls:")
        print(option_chain['calls'].to_string(index=False))
        print("\nPuts:")
        print(option_chain['puts'].to_string(index=False))
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_marketdataapp_provider.py <path_to_settings.yaml>")
    else:
        main(sys.argv[1])
