"""Test market data providers to identify issues."""

import traceback


def test_yfinance():
    print("=" * 60)
    print("Testing YFinanceProvider")
    print("=" * 60)

    from goldflipper.data.market.providers.yfinance_provider import YFinanceProvider

    provider = YFinanceProvider()

    # Test 1: Get option chain
    print("\n--- Test 1: Option Chain ---")
    try:
        chain = provider.get_option_chain("SPY")
        calls = chain["calls"]
        puts = chain["puts"]
        print(f"Calls: {len(calls)} rows")
        print(f"Puts: {len(puts)} rows")
        if not calls.empty:
            print(f"First call symbol: {calls['symbol'].iloc[0]}")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()

    # Test 2: Get option quote using actual strike from chain
    print("\n--- Test 2: Option Quote (using actual strike from chain) ---")
    try:
        # Get actual contract symbol from chain
        if not calls.empty:
            actual_symbol = calls["symbol"].iloc[0]
            actual_strike = calls["strike"].iloc[0]
            print(f"Testing with actual contract: {actual_symbol} (strike={actual_strike})")
            quote = provider.get_option_quote(actual_symbol)
            print(f"Quote type: {type(quote)}")
            print(f"Quote empty: {quote.empty if hasattr(quote, 'empty') else 'N/A'}")
            if hasattr(quote, "empty") and not quote.empty:
                print(f"Quote bid: {quote['bid'].iloc[0]}, ask: {quote['ask'].iloc[0]}")
        else:
            print("No calls available to test")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()

    # Test 3: Get option quote - test OCC parsing
    print("\n--- Test 3: Option Quote (verify parsing) ---")
    try:
        # Use a contract we know exists
        if not calls.empty:
            test_symbol = calls["symbol"].iloc[5] if len(calls) > 5 else calls["symbol"].iloc[0]
            print(f"Testing: {test_symbol}")
            quote = provider.get_option_quote(test_symbol)
            print(f"Quote empty: {quote.empty}")
            if not quote.empty:
                print(f"Success! Got quote with bid={quote['bid'].iloc[0]}")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()

    # Test 4: Get expirations
    print("\n--- Test 4: Option Expirations ---")
    try:
        expirations = provider.get_option_expirations("SPY")
        print(f"Expirations: {expirations[:5] if expirations else 'None'}...")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()


def test_alpaca():
    print("\n" + "=" * 60)
    print("Testing AlpacaProvider")
    print("=" * 60)

    from goldflipper.data.market.providers.alpaca_provider import AlpacaProvider
    from goldflipper.utils.exe_utils import get_settings_path

    config_path = str(get_settings_path())
    print(f"Config path: {config_path}")

    try:
        provider = AlpacaProvider(config_path)
        print("AlpacaProvider initialized successfully")
    except Exception as e:
        print(f"ERROR initializing AlpacaProvider: {e}")
        traceback.print_exc()
        return

    # Test 1: Get stock price
    print("\n--- Test 1: Stock Price ---")
    try:
        price = provider.get_stock_price("SPY")
        print(f"Price: {price} (type: {type(price).__name__})")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()

    # Test 2: Get option chain
    print("\n--- Test 2: Option Chain ---")
    try:
        chain = provider.get_option_chain("SPY")
        calls = chain["calls"]
        puts = chain["puts"]
        print(f"Calls: {len(calls)} rows")
        print(f"Puts: {len(puts)} rows")
        if not calls.empty:
            print(f"Calls columns: {calls.columns.tolist()}")
            print(f"First call symbol: {calls['symbol'].iloc[0]}")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()

    # Test 3: Get option quote
    print("\n--- Test 3: Option Quote ---")
    try:
        quote = provider.get_option_quote("SPY251211C00590000")
        print(f"Quote type: {type(quote)}")
        print(f"Quote empty: {quote.empty if hasattr(quote, 'empty') else 'N/A'}")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()

    # Test 4: Get option expirations
    print("\n--- Test 4: Option Expirations ---")
    try:
        expirations = provider.get_option_expirations("SPY")
        print(f"Expirations: {expirations[:5] if expirations else 'Empty list'}")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()


def test_manager():
    print("\n" + "=" * 60)
    print("Testing MarketDataManager")
    print("=" * 60)

    from goldflipper.data.market.manager import MarketDataManager

    try:
        manager = MarketDataManager()
        print(f"Manager initialized with providers: {list(manager.providers.keys())}")
        print(f"Primary provider: {manager.config['primary_provider']}")
    except Exception as e:
        print(f"ERROR initializing MarketDataManager: {e}")
        traceback.print_exc()
        return

    # Test option quote through manager
    print("\n--- Test: Option Quote via Manager ---")
    try:
        quote = manager.get_option_quote("SPY251211C00590000")
        print(f"Quote result: {quote}")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    test_yfinance()
    test_alpaca()
    test_manager()
