import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
from goldflipper.data.market.manager import MarketDataManager
from goldflipper.utils.display import TerminalDisplay as display

logging.basicConfig(level=logging.INFO)

def test_market_data():
    """Test core market data functionality"""
    
    # Get absolute path to config file
    config_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'goldflipper',
        'config',
        'settings.yaml'
    ))
    
    # Initialize manager with correct config path
    manager = MarketDataManager(config_path=config_path)
    
    # Test stock price
    symbol = "SPY"
    print(f"\nTesting stock price for {symbol}...")
    price = manager.get_stock_price(symbol)
    print(f"Stock price: ${price:.2f}" if price else "Failed to get stock price")
    
    # Test option quote
    contract = "AAPL250103C00255000"  # Example contract
    print(f"\nTesting option quote for {contract}...")
    quote = manager.get_option_quote(contract)
    if quote:
        print("Option Quote:")
        print(f"Premium: ${quote['premium']:.2f}")
        print(f"Bid: ${quote['bid']:.2f}")
        print(f"Ask: ${quote['ask']:.2f}")
    else:
        print("Failed to get option quote")

if __name__ == "__main__":
    try:
        test_market_data()
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nTest failed: {str(e)}") 