import logging

from alpaca.trading.client import TradingClient

from goldflipper.config.config import config

# Debugging output - only log if needed
# print(f"Python path: {sys.path}")
# print(f"Current working directory: {os.getcwd()}")

# ==================================================
# ALPACA CLIENT SETUP
# ==================================================
# This module sets up the Alpaca trading client to allow Goldflipper to place real
# buy and sell orders. The API key, secret key, and base URL are loaded from
# the configuration file locally within the get_alpaca_client function.

_client_instance = None


def get_alpaca_client():
    active_account = config.get("alpaca", "active_account")
    account = config.get("alpaca", "accounts")[active_account]

    # Only create new instance in debug mode, otherwise use singleton
    if logging.getLogger().getEffectiveLevel() <= logging.DEBUG:
        logging.debug(f"Creating new Alpaca client for account: '{active_account}' (debug mode: new instance per call)")
        return create_client_from_account(account, active_account)

    global _client_instance
    if _client_instance is None:
        logging.info(f"Initializing Alpaca client for account: '{active_account}'")
        _client_instance = create_client_from_account(account, active_account)
    return _client_instance


def reset_client():
    global _client_instance
    _client_instance = None
    logging.debug("Alpaca trading client reset")


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
    api_key = account["api_key"]
    secret_key = account["secret_key"]
    base_url = account["base_url"]

    # Remove '/v2' from base_url if present, as SDK adds it automatically.
    base_url = base_url.replace("/v2", "")

    # Only log full API key in debug mode
    if logging.getLogger().getEffectiveLevel() <= logging.DEBUG:
        logging.debug(
            f"Creating Alpaca client - Account: '{active_account}', "
            f"API Key: {api_key[:4]}...{api_key[-4:]}, "
            f"Paper Trading: {'paper' in active_account}"
        )
    else:
        logging.info(f"Creating Alpaca client - Account: '{active_account}', Paper Trading: {'paper' in active_account}")

    # Initialize the client with the correct parameters.
    client = TradingClient(
        api_key=api_key,
        secret_key=secret_key,
        paper="paper" in active_account.lower(),  # Enable paper trading if active account contains 'paper'
        url_override=base_url,
    )

    return client
