# You can use Python's help function
import yfinance as yf
# help(yf.Ticker.option_chain)

# Or check the docstring
print(yf.Ticker.option_chain.__doc__)

ticker = yf.Ticker("SPY")
chain = ticker.option_chain('2025-01-03')

print(chain)