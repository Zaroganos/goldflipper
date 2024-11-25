# You can use Python's help function
import yfinance as yf
# help(yf.Ticker.option_chain)

# Or check the docstring
print(yf.Ticker.option_chain.__doc__)

ticker = yf.Ticker("AAPL")
chain = ticker.option_chain('2024-12-06')

# Try to access Greeks (if available)
try:
    # For calls
    greeks_calls = chain.calls[['strike', 'delta', 'gamma', 'theta', 'vega']]
    print("Call Options Greeks:")
    print(greeks_calls.head())
    
    # For puts
    greeks_puts = chain.puts[['strike', 'delta', 'gamma', 'theta', 'vega']]
    print("\nPut Options Greeks:")
    print(greeks_puts.head())
except KeyError as e:
    print(f"Some Greeks data not available: {e}")