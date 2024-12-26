import sys
import os
from alpaca.trading.client import TradingClient
from goldflipper.config.config import config

# Debugging output
print(f"Python path: {sys.path}")
print(f"Current working directory: {os.getcwd()}")

# ==================================================
# ALPACA CLIENT SETUP
# ==================================================
# This module sets up the Alpaca trading client to allow the bot to place real
# buy and sell orders. The API key, secret key, and base URL are loaded from
# the configuration file locally within the get_alpaca_client function.


def get_alpaca_client():
    """
    Initialize and return the Alpaca Trading Client using the active account.

    Returns:
    - TradingClient: The Alpaca client for trading.
    """
    # Get the active account name
    active_account = config.get('alpaca', 'active_account')
    
    # Get the account details
    accounts = config.get('alpaca', 'accounts')
    if active_account not in accounts:
        raise ValueError(f"Active account '{active_account}' not found in configuration")
    
    account = accounts[active_account]
    
    # Get credentials for the active account
    api_key = account['api_key']
    secret_key = account['secret_key']
    base_url = account['base_url']

    # Remove '/v2' from base_url if present, as SDK adds it automatically
    base_url = base_url.replace('/v2', '')

    # Initialize the client with the correct parameters
    client = TradingClient(
        api_key=api_key,
        secret_key=secret_key,
        paper=True if 'paper' in active_account else False,  # Set paper trading based on account name
        url_override=base_url
    )
    return client
