import sys
import os
from alpaca.trading.client import TradingClient

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
    from goldflipper.config.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL

    # Initialize the client with the correct parameters
    client = TradingClient(
        api_key=ALPACA_API_KEY,
        secret_key=ALPACA_SECRET_KEY,
        paper=True,  # Set to True for paper trading environment
        url_override=ALPACA_BASE_URL  # Override the API URL if needed
    )
    return client
