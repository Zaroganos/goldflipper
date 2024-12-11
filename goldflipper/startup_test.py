import logging
import yfinance as yf
from datetime import datetime
import sys
import os
import requests

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)

from goldflipper.alpaca_client import get_alpaca_client
from goldflipper.config.config import config

def test_alpaca_connection():
    """Test Alpaca API connectivity and account status."""
    try:
        client = get_alpaca_client()
        account = client.get_account()
        
        # Basic account validation
        if not account:
            return False, "Could not retrieve account information"
            
        # Check if account is active
        if account.status != 'ACTIVE':
            return False, f"Account status is {account.status}, not ACTIVE"
            
        # Check trading capabilities
        if not account.trading_blocked and account.account_blocked:
            return False, "Account is blocked from trading"
            
        return True, {
            "account_id": account.id,
            "cash": account.cash,
            "options_level": account.options_trading_level,
            "pattern_day_trader": account.pattern_day_trader
        }
        
    except Exception as e:
        return False, f"Alpaca API test failed: {str(e)}"

def test_yfinance_connection():
    """Test yfinance API connectivity using a known reliable ticker."""
    try:
        # Test with SPY as it's highly reliable
        ticker = yf.Ticker("SPY")
        info = ticker.info
        
        if not info:
            return False, "Could not retrieve ticker information"
            
        # Test option chain access
        chain = ticker.option_chain(ticker.options[0])
        if chain is None:
            return False, "Could not retrieve option chain"
            
        return True, {
            "current_price": info.get('regularMarketPrice'),
            "market_state": info.get('marketState'),
            "exchange": info.get('exchange')
        }
        
    except Exception as e:
        return False, f"yfinance API test failed: {str(e)}"

def test_alpaca_api_direct():
    """Test Alpaca API connectivity directly using HTTP request."""
    try:
        # Get credentials from config
        api_key = config.get('alpaca', 'api_key')
        secret_key = config.get('alpaca', 'secret_key')
        base_url = config.get('alpaca', 'base_url')
        
        # Set up headers
        headers = {
            'APCA-API-KEY-ID': api_key,
            'APCA-API-SECRET-KEY': secret_key
        }
        
        # Make request
        response = requests.get(f"{base_url}/account", headers=headers)
        
        if response.status_code == 200:
            account_data = response.json()
            return True, {
                "status_code": response.status_code,
                "account_status": account_data.get('status'),
                "currency": account_data.get('currency'),
                "cash": account_data.get('cash'),
                "portfolio_value": account_data.get('portfolio_value')
            }
        else:
            return False, f"API request failed with status code: {response.status_code}, Response: {response.text}"
            
    except Exception as e:
        return False, f"Direct API test failed: {str(e)}"

def run_startup_tests():
    """Run all startup tests and return comprehensive results."""
    logging.info("Running startup self-tests...")
    
    test_results = {
        "timestamp": datetime.now().isoformat(),
        "tests": {}
    }
    
    # Test Alpaca connection through SDK
    success, alpaca_result = test_alpaca_connection()
    test_results["tests"]["alpaca_sdk"] = {
        "success": success,
        "result": alpaca_result
    }
    
    # Test Alpaca connection through direct API
    success, alpaca_api_result = test_alpaca_api_direct()
    test_results["tests"]["alpaca_api"] = {
        "success": success,
        "result": alpaca_api_result
    }
    
    # Test yfinance connection
    success, yfinance_result = test_yfinance_connection()
    test_results["tests"]["yfinance"] = {
        "success": success,
        "result": yfinance_result
    }
    
    # Overall status
    test_results["all_passed"] = all(
        test["success"] for test in test_results["tests"].values()
    )
    
    return test_results

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = run_startup_tests()
    
    print("\nStartup Self-Test Results:")
    print("=" * 50)
    
    for test_name, test_data in results["tests"].items():
        print(f"\n{test_name.upper()} Test:")
        print(f"Status: {'PASSED' if test_data['success'] else 'FAILED'}")
        print(f"Details: {test_data['result']}")
    
    print("\nOverall Status:", "PASSED" if results["all_passed"] else "FAILED")
