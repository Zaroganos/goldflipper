import yfinance as yf

def test_yfinance():
    # Test with a known ticker
    ticker = "AAPL"
    stock = yf.Ticker(ticker)
    
    print("\nTesting yfinance API...")
    print(f"\nTicker: {ticker}")
    
    # Print available info keys
    print("\nAvailable info keys:")
    info = stock.info
    print(list(info.keys()))
    
    # Print current price
    print("\nCurrent price methods:")
    print(f"info['currentPrice']: {info.get('currentPrice')}")
    print(f"info['regularMarketPrice']: {info.get('regularMarketPrice')}")
    print(f"info['lastPrice']: {info.get('lastPrice')}")
    
    # Print option chain info
    print("\nOption chain:")
    dates = stock.options
    print(f"Available dates: {dates}")
    
    if dates:
        chain = stock.option_chain(dates[0])
        print("\nCall options columns:")
        print(chain.calls.columns.tolist())
        print("\nFirst call option:")
        print(chain.calls.iloc[0])

if __name__ == "__main__":
    test_yfinance() 