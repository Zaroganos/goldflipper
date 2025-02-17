import logging
import yfinance as yf
from datetime import datetime
import sys
import os
import requests

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

from .alpaca_client import get_alpaca_client
from .config.config import config

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

def test_yfinance_ticker():
    """Test yfinance Ticker API connectivity."""
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
        return False, f"yfinance Ticker API test failed: {str(e)}"

def test_yfinance_download():
    """Test yfinance download functionality."""
    try:
        df = yf.download("SPY", period="1d", progress=False)
        
        if df.empty:
            return False, "Could not download price data"
            
        return True, {
            "rows_retrieved": len(df),
            "columns": list(df.columns),
            "latest_close": float(df['Close'].iloc[-1])
        }
        
    except Exception as e:
        return False, f"yfinance download test failed: {str(e)}"

def test_alpaca_api_direct():
    """Test Alpaca API connectivity directly using HTTP request."""
    try:
        # Get the active account details
        active_account = config.get('alpaca', 'active_account')
        accounts = config.get('alpaca', 'accounts')
        if active_account not in accounts:
            return False, f"Active account '{active_account}' not found in configuration"
        
        account = accounts[active_account]
        
        # Get credentials for the active account
        api_key = account['api_key']
        secret_key = account['secret_key']
        base_url = account['base_url']
        
        # Set up headers
        headers = {
            'APCA-API-KEY-ID': api_key,
            'APCA-API-SECRET-KEY': secret_key
        }
        
        # Make request
        response = requests.get(f"{base_url}/account", headers=headers)
        
        if response.status_code == 200:
            account_data = response.json()
            nickname = account.get('nickname', active_account.replace('_', ' ').title())
            return True, {
                "account": nickname,
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

def test_marketdata_api():
    """Test MarketData.app API connectivity and service status."""
    try:
        # Use the status endpoint which doesn't require authentication
        response = requests.get("https://api.marketdata.app/status/")
        
        if response.status_code != 200:
            return False, f"MarketData.app API returned status code: {response.status_code}"
            
        data = response.json()
        
        # First check if we got a valid response
        if data.get('s') != 'ok':
            return False, "MarketData.app API returned non-ok status"
            
        # Look for the two specific API services we care about
        services = data.get('service', [])
        online_statuses = data.get('online', [])
        
        # Success if we got a valid response with services
        if not services or not online_statuses:
            return False, "Could not retrieve service information"
            
        return True, {
            'services': list(zip(services, online_statuses))
        }
        
    except Exception as e:
        return False, f"MarketData.app API test failed: {str(e)}"

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
    
    # Test yfinance Ticker functionality
    success, yfinance_ticker_result = test_yfinance_ticker()
    test_results["tests"]["yfinance_ticker"] = {
        "success": success,
        "result": yfinance_ticker_result
    }
    
    # Test yfinance download functionality
    success, yfinance_download_result = test_yfinance_download()
    test_results["tests"]["yfinance_download"] = {
        "success": success,
        "result": yfinance_download_result
    }
    
    # Test MarketData.app API
    success, marketdata_result = test_marketdata_api()
    test_results["tests"]["marketdata.app"] = {
        "success": success,
        "result": marketdata_result
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
