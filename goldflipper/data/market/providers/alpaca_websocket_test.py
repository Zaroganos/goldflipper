from alpaca.data.live import StockDataStream
import asyncio
import logging
from goldflipper.utils.logging_setup import configure_logging

configure_logging(console_mode=True, level_override=logging.DEBUG)

# Your API credentials
API_KEY = "PKXATZMQYM3AIMOS9JAE"
SECRET_KEY = "lfujbWBWJQNMoHzioZNEyD0jRXKIXUoxqGQjXxmR"

async def main():
    # Initialize
    stream = StockDataStream(
        api_key=API_KEY,
        secret_key=SECRET_KEY
    )
    
    async def quote_handler(q):
        print(f"Quote received: {q}")
        
    async def trade_handler(t):
        print(f"Trade received: {t}")
    
    # Subscribe to AAPL
    stream.subscribe_quotes(quote_handler, "AAPL")
    stream.subscribe_trades(trade_handler, "AAPL")
    
    try:
        # Start streaming using _run_forever directly
        await stream._run_forever()
    except Exception as e:
        print(f"Error: {e}")
        raise  # Let's see the full traceback

if __name__ == "__main__":
    asyncio.run(main())
