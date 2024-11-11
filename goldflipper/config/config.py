import os

# Alpaca API credentials
ALPACA_API_KEY = 'PKJTEWFLB1XI1Y4BS6WW'
ALPACA_SECRET_KEY = 'cNodK08udpSEk3JwA3l45Rqlsa4NNBgzyzafyWvf'
ALPACA_BASE_URL = 'https://paper-api.alpaca.markets'  # Use the paper trading URL for testing

# Data paths
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
RAW_DATA_DIR = os.path.join(DATA_DIR, 'raw')
PROCESSED_DATA_DIR = os.path.join(DATA_DIR, 'processed')

# Trading parameters
TRADE_SYMBOL = 'SPY'  # Replace with the desired trading symbol
TRADE_QUANTITY = 100  # Replace with the desired trade quantity

# Logging settings
LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'app.log')
LOG_LEVEL = 'INFO'  # Change to 'DEBUG' for more detailed logging

# Other configuration options
# Add more configuration settings as needed
