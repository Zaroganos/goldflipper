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
    Initialize and return the Alpaca Trading Client.

    Returns:
    - TradingClient: The Alpaca client for trading.
    """
    # Get credentials using the same method as the direct API test
    api_key = config.get('alpaca', 'api_key')
    secret_key = config.get('alpaca', 'secret_key')
    base_url = config.get('alpaca', 'base_url')

    # Remove '/v2' from base_url if present, as SDK adds it automatically
    base_url = base_url.replace('/v2', '')

    # Initialize the client with the correct parameters
    client = TradingClient(
        api_key=api_key,
        secret_key=secret_key,
        paper=True,  # Set to True for paper trading environment
        url_override=base_url
    )
    return client
