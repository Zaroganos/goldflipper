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

_client_instance = None

def get_alpaca_client():
    # For debugging purposes, always create a new client instance.
    active_account = config.get('alpaca', 'active_account')
    account = config.get('alpaca', 'accounts')[active_account]
    print(f"[DEBUG] Creating Alpaca client for active account: '{active_account}' using API key ending in: {account['api_key'][-4:]}")
    return create_client_from_account(account, active_account)

def reset_client():
    global _client_instance
    _client_instance = None
    print("[DEBUG] reset_client() called.")

def create_client_from_account(account, active_account):
    """
    Initialize and return the Alpaca Trading Client using the active account.

    Args:
        account (dict): The account information (api_key, secret_key, base_url, etc.)
        active_account (str): The account key from the configuration used to determine mode.

    Returns:
        TradingClient: The Alpaca client for trading.
    """
    # Get credentials for the active account.
    api_key = account['api_key']
    secret_key = account['secret_key']
    base_url = account['base_url']

    # Remove '/v2' from base_url if present, as SDK adds it automatically.
    base_url = base_url.replace('/v2', '')

    # Initialize the client with the correct parameters.
    print(f"[DEBUG] In create_client_from_account: active_account='{active_account}', paper_flag={'True' if 'paper' in active_account else 'False'}")
    client = TradingClient(
        api_key=api_key,
        secret_key=secret_key,
        paper=True if 'paper' in active_account else False,  # Enable paper trading if active account contains 'paper'
        url_override=base_url
    )
    return client
