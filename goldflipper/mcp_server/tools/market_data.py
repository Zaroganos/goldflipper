"""Market data query tools — stock prices, option quotes, expirations, earnings."""

from goldflipper.mcp_server.server import mcp
from goldflipper.mcp_server.context import ctx


@mcp.tool
def get_stock_price(symbol: str) -> dict:
    """Get the current stock price for a ticker symbol.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'SPY', 'TSLA')

    Returns:
        Dict with symbol and price, or error message.
    """
    price = ctx.market_data.get_stock_price(symbol.upper())
    if price is None:
        return {"error": f"Could not get price for {symbol}", "symbol": symbol.upper()}
    return {"symbol": symbol.upper(), "price": float(price)}


@mcp.tool
def get_option_quote(contract_symbol: str) -> dict:
    """Get an option quote including bid, ask, last, mid, Greeks, volume, and open interest.

    Args:
        contract_symbol: OCC option symbol (e.g., 'AAPL250117C00150000')

    Returns:
        Dict with bid, ask, last, mid, delta, theta, volume, open_interest.
    """
    quote = ctx.market_data.get_option_quote(contract_symbol.upper())
    if quote is None:
        return {"error": f"No quote available for {contract_symbol}", "contract": contract_symbol.upper()}
    return {"contract": contract_symbol.upper(), **quote}


@mcp.tool
def get_option_expirations(symbol: str) -> dict:
    """Get available option expiration dates for a stock symbol.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'SPY')

    Returns:
        Dict with symbol and list of expiration dates.
    """
    expirations = ctx.market_data.get_option_expirations(symbol.upper())
    if not expirations:
        return {"symbol": symbol.upper(), "expirations": [], "note": "No expirations found"}
    # Convert dates to strings if they aren't already
    exp_strings = [str(e) for e in expirations]
    return {"symbol": symbol.upper(), "expirations": exp_strings, "count": len(exp_strings)}


@mcp.tool
def get_next_earnings(symbol: str) -> dict:
    """Get the next upcoming earnings date for a stock symbol.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'TSLA')

    Returns:
        Dict with symbol and next earnings date (or null if unavailable).
    """
    date = ctx.market_data.get_next_earnings_date(symbol.upper())
    return {"symbol": symbol.upper(), "next_earnings_date": str(date) if date else None}


@mcp.tool
def get_previous_close(symbol: str) -> dict:
    """Get the previous trading day's closing price for a stock symbol.

    Args:
        symbol: Stock ticker symbol (e.g., 'SPY', 'AAPL')

    Returns:
        Dict with symbol and previous close price.
    """
    close = ctx.market_data.get_previous_close(symbol.upper())
    if close is None:
        return {"error": f"Could not get previous close for {symbol}", "symbol": symbol.upper()}
    return {"symbol": symbol.upper(), "previous_close": float(close)}
