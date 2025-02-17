import sys
import os
from datetime import datetime
import pandas as pd
import yaml

# Add the project root to the PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
if project_root not in sys.path:

from ....data.market.providers.marketdataapp_provider import MarketDataAppProvider

def main():
    """Interactive test tool for MarketDataApp provider"""
    
    # Initialize the provider with config
    config_path = os.path.join(project_root, "goldflipper", "config", "settings.yaml")
    
    if not os.path.exists(config_path):
        print(f"Error: Config file not found at {config_path}")
        print(f"Current directory: {os.getcwd()}")
        print(f"Project root: {project_root}")
        return
        
    provider = MarketDataAppProvider(config_path)
    
    while True:
        print("\nMarketDataApp Test Tool")
        print("----------------------")
        print("1. Enter Symbol/Ticker")
        print("2. Enter Option Contract")
        print("3. Get Full Option Chain")
        print("4. Exit")
        
        choice = input("\nEnter your choice (1-4): ")
        
        if choice == "1":
            symbol = input("\nEnter stock symbol (e.g., AAPL): ").strip().upper()
            try:
                price = provider.get_stock_price(symbol)
                print(f"\nLast price for {symbol}: ${price:.2f}")
            except Exception as e:
                print(f"\nError: {str(e)}")
                
        elif choice == "2":
            contract = input("\nEnter option contract (e.g., AAPL250117C00150000): ").strip().upper()
            try:
                # Get Greeks
                greeks = provider.get_option_greeks(contract)
                
                # Get option chain to find this specific contract's data
                symbol = contract[:4]  # Extract symbol from contract
                expiry = contract[4:10]  # Extract date from contract
                formatted_date = f"20{expiry[:2]}-{expiry[2:4]}-{expiry[4:6]}"
                chain = provider.get_option_chain(symbol, formatted_date)
                
                # Find this specific contract in the chain
                contract_type = 'calls' if 'C' in contract else 'puts'
                contract_data = chain[contract_type][chain[contract_type]['optionSymbol'] == contract].iloc[0]
                
                print(f"\nOption Data for {contract}:")
                print(f"\nPrice Data:")
                print(f"Last: ${contract_data['last']:.2f}")
                print(f"Bid: ${contract_data['bid']:.2f}")
                print(f"Ask: ${contract_data['ask']:.2f}")
                print(f"Volume: {int(contract_data['volume'])}")
                print(f"Open Interest: {int(contract_data['openInterest'])}")
                print(f"Implied Volatility: {contract_data['impliedVolatility']:.2%}")
                
                print("\nGreeks:")
                for greek, value in greeks.items():
                    print(f"{greek.capitalize()}: {value:.4f}")
                
            except Exception as e:
                print(f"\nError: {str(e)}")
                
        elif choice == "3":
            symbol = input("\nEnter stock symbol (e.g., AAPL): ").strip().upper()
            expiry = input("\nEnter expiration date (YYYY-MM-DD) or press Enter for nearest: ").strip()
            try:
                chain = provider.get_option_chain(symbol, expiry if expiry else None)
                
                print(f"\nOption Chain for {symbol}")
                print("\nCALLS:")
                print(chain['calls'].to_string())
                print("\nPUTS:")
                print(chain['puts'].to_string())
                
            except Exception as e:
                print(f"\nError: {str(e)}")
                
        elif choice == "4":
            print("\nExiting...")
            break
            
        else:
            print("\nInvalid choice. Please try again.")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()
